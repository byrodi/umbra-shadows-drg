#include "BPForgeCommandlet.h"

#include "AssetRegistryModule.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Components/PanelSlot.h"
#include "Components/PanelWidget.h"
#include "Dom/JsonObject.h"
#include "EdGraph/EdGraph.h"
#include "Components/SceneCaptureComponent2D.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SCS_Node.h"
#include "Engine/SceneCapture2D.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "ImageUtils.h"
#include "K2Node_CallFunction.h"
#include "K2Node_ClassDynamicCast.h"
#include "K2Node_ComponentBoundEvent.h"
#include "K2Node_DynamicCast.h"
#include "K2Node_Event.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_MacroInstance.h"
#include "K2Node_MakeArray.h"
#include "K2Node_Self.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ShaderCompiler.h"
#include "UObject/Interface.h"
#include "UObject/Package.h"
#include "WidgetBlueprint.h"

DEFINE_LOG_CATEGORY_STATIC(LogBPForge, Log, All);

namespace
{
	typedef TSharedPtr<FJsonObject> FJson;

	bool GFailed = false;

	void Fail(const FString& Message)
	{
		GFailed = true;
		UE_LOG(LogBPForge, Error, TEXT("%s"), *Message);
	}

	UClass* FindClassByPath(const FString& Path)
	{
		UClass* Class = LoadObject<UClass>(nullptr, *Path);
		if (!Class)
		{
			Fail(FString::Printf(TEXT("Class not found: %s"), *Path));
		}
		return Class;
	}

	bool MakePinType(const FJson& J, FEdGraphPinType& Out)
	{
		const FString Type = J->GetStringField(TEXT("type"));
		Out = FEdGraphPinType();
		if (Type == TEXT("float")) { Out.PinCategory = UEdGraphSchema_K2::PC_Float; }
		else if (Type == TEXT("int")) { Out.PinCategory = UEdGraphSchema_K2::PC_Int; }
		else if (Type == TEXT("bool")) { Out.PinCategory = UEdGraphSchema_K2::PC_Boolean; }
		else if (Type == TEXT("string")) { Out.PinCategory = UEdGraphSchema_K2::PC_String; }
		else if (Type == TEXT("text")) { Out.PinCategory = UEdGraphSchema_K2::PC_Text; }
		else if (Type == TEXT("name")) { Out.PinCategory = UEdGraphSchema_K2::PC_Name; }
		else
		{
			UObject* Sub = LoadObject<UObject>(nullptr, *J->GetStringField(TEXT("class")));
			if (!Sub)
			{
				Fail(FString::Printf(TEXT("Type object not found: %s"), *J->GetStringField(TEXT("class"))));
				return false;
			}
			if (Type == TEXT("object")) { Out.PinCategory = UEdGraphSchema_K2::PC_Object; }
			else if (Type == TEXT("class")) { Out.PinCategory = UEdGraphSchema_K2::PC_Class; }
			else if (Type == TEXT("interface")) { Out.PinCategory = UEdGraphSchema_K2::PC_Interface; }
			else if (Type == TEXT("struct")) { Out.PinCategory = UEdGraphSchema_K2::PC_Struct; }
			else
			{
				Fail(FString::Printf(TEXT("Unknown pin type: %s"), *Type));
				return false;
			}
			Out.PinSubCategoryObject = Sub;
		}
		bool bFlag = false;
		if (J->TryGetBoolField(TEXT("array"), bFlag) && bFlag) { Out.ContainerType = EPinContainerType::Array; }
		if (J->TryGetBoolField(TEXT("ref"), bFlag) && bFlag) { Out.bIsReference = true; Out.bIsConst = true; }
		return true;
	}

	UK2Node_FunctionEntry* FindEntry(UEdGraph* Graph)
	{
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (UK2Node_FunctionEntry* Entry = Cast<UK2Node_FunctionEntry>(Node))
			{
				return Entry;
			}
		}
		return nullptr;
	}

	UK2Node_FunctionResult* FindResult(UEdGraph* Graph)
	{
		for (UEdGraphNode* Node : Graph->Nodes)
		{
			if (UK2Node_FunctionResult* Result = Cast<UK2Node_FunctionResult>(Node))
			{
				return Result;
			}
		}
		return nullptr;
	}

	UEdGraph* FindGraph(UBlueprint* BP, const FString& Name)
	{
		if (Name == TEXT("EventGraph"))
		{
			return FBlueprintEditorUtils::FindEventGraph(BP);
		}
		TArray<UEdGraph*> Graphs;
		BP->GetAllGraphs(Graphs);
		for (UEdGraph* Graph : Graphs)
		{
			if (Graph->GetName() == Name)
			{
				return Graph;
			}
		}
		return nullptr;
	}

	/** Adds a function graph with the given inputs and outputs. */
	void AddFunction(UBlueprint* BP, const FJson& J)
	{
		const FString Name = J->GetStringField(TEXT("name"));
		UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(BP, FName(*Name), UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
		FBlueprintEditorUtils::AddFunctionGraph<UClass>(BP, Graph, true, nullptr);
		UK2Node_FunctionEntry* Entry = FindEntry(Graph);
		if (!Entry)
		{
			Fail(FString::Printf(TEXT("No entry node in function %s"), *Name));
			return;
		}
		const TArray<TSharedPtr<FJsonValue>>* Pins = nullptr;
		if (J->TryGetArrayField(TEXT("inputs"), Pins))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Pins)
			{
				FEdGraphPinType PinType;
				if (MakePinType(Value->AsObject(), PinType))
				{
					Entry->CreateUserDefinedPin(FName(*Value->AsObject()->GetStringField(TEXT("name"))), PinType, EGPD_Output, false);
				}
			}
		}
		if (J->TryGetArrayField(TEXT("outputs"), Pins) && Pins->Num() > 0)
		{
			UK2Node_FunctionResult* Result = FBlueprintEditorUtils::FindOrCreateFunctionResultNode(Entry);
			for (const TSharedPtr<FJsonValue>& Value : *Pins)
			{
				FEdGraphPinType PinType;
				if (MakePinType(Value->AsObject(), PinType))
				{
					Result->CreateUserDefinedPin(FName(*Value->AsObject()->GetStringField(TEXT("name"))), PinType, EGPD_Input, false);
				}
			}
		}
	}

	bool Compile(UBlueprint* BP)
	{
		FCompilerResultsLog Results;
		Results.bSilentMode = true;
		FKismetEditorUtilities::CompileBlueprint(BP, EBlueprintCompileOptions::SkipGarbageCollection, &Results);
		for (const TSharedRef<FTokenizedMessage>& Message : Results.Messages)
		{
			if (Message->GetSeverity() <= EMessageSeverity::Warning)
			{
				UE_LOG(LogBPForge, Warning, TEXT("[%s] %s"), *BP->GetName(), *Message->ToText().ToString());
			}
		}
		if (Results.NumErrors > 0 || BP->Status == BS_Error)
		{
			Fail(FString::Printf(TEXT("Blueprint %s failed to compile (%d errors)"), *BP->GetName(), Results.NumErrors));
			return false;
		}
		return true;
	}

	bool Save(UBlueprint* BP)
	{
		UPackage* Package = BP->GetOutermost();
		Package->MarkPackageDirty();
		const FString Filename = FPackageName::LongPackageNameToFilename(Package->GetName(), FPackageName::GetAssetPackageExtension());
		if (!UPackage::SavePackage(Package, BP, RF_Public | RF_Standalone, *Filename, GError, nullptr, false, true, SAVE_NoError))
		{
			Fail(FString::Printf(TEXT("Could not save %s"), *Filename));
			return false;
		}
		UE_LOG(LogBPForge, Display, TEXT("Saved %s"), *Filename);
		return true;
	}

	void ImportProps(UObject* Object, const FJson& Props)
	{
		for (const auto& Pair : Props->Values)
		{
			FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Pair.Key));
			if (!Property)
			{
				Fail(FString::Printf(TEXT("Property %s not found on %s"), *Pair.Key, *Object->GetClass()->GetName()));
				continue;
			}
			const FString Text = Pair.Value->AsString();
			if (!Property->ImportText(*Text, Property->ContainerPtrToValuePtr<void>(Object), PPF_None, Object))
			{
				Fail(FString::Printf(TEXT("Could not import %s = %s"), *Pair.Key, *Text));
			}
		}
	}

	void BuildWidget(UWidgetBlueprint* BP, const FJson& J, UPanelWidget* Parent)
	{
		UClass* Class = FindClassByPath(J->GetStringField(TEXT("class")));
		if (!Class)
		{
			return;
		}
		UWidget* Widget = BP->WidgetTree->ConstructWidget<UWidget>(Class, FName(*J->GetStringField(TEXT("name"))));
		bool bVariable = false;
		J->TryGetBoolField(TEXT("var"), bVariable);
		Widget->bIsVariable = bVariable;
		const FJson* Props = nullptr;
		if (J->TryGetObjectField(TEXT("props"), Props))
		{
			ImportProps(Widget, *Props);
		}
		if (Parent)
		{
			UPanelSlot* Slot = Parent->AddChild(Widget);
			if (Slot && J->TryGetObjectField(TEXT("slot"), Props))
			{
				ImportProps(Slot, *Props);
			}
		}
		else
		{
			BP->WidgetTree->RootWidget = Widget;
		}
		const TArray<TSharedPtr<FJsonValue>>* Children = nullptr;
		if (J->TryGetArrayField(TEXT("children"), Children))
		{
			UPanelWidget* Panel = Cast<UPanelWidget>(Widget);
			if (!Panel)
			{
				Fail(FString::Printf(TEXT("%s cannot have children"), *Widget->GetName()));
				return;
			}
			for (const TSharedPtr<FJsonValue>& Child : *Children)
			{
				BuildWidget(BP, Child->AsObject(), Panel);
			}
		}
	}

	struct FGraphBuilder
	{
		UBlueprint* BP;
		UEdGraph* Graph;
		const UEdGraphSchema_K2* Schema;
		TMap<FString, UEdGraphNode*> Nodes;
		FString Where;

		template <typename T>
		T* Spawn(TFunctionRef<void(T*)> Init)
		{
			FGraphNodeCreator<T> Creator(*Graph);
			T* Node = Creator.CreateNode(false);
			Init(Node);
			Creator.Finalize();
			return Node;
		}

		UEdGraphNode* MakeNode(const FJson& J)
		{
			const FString Kind = J->GetStringField(TEXT("k"));
			FString ClassPath;
			J->TryGetStringField(TEXT("class"), ClassPath);
			FString Name;
			J->TryGetStringField(TEXT("name"), Name);

			if (Kind == TEXT("event"))
			{
				UClass* Class = FindClassByPath(ClassPath);
				if (!Class) { return nullptr; }
				return Spawn<UK2Node_Event>([&](UK2Node_Event* Node)
				{
					Node->EventReference.SetExternalMember(FName(*Name), Class);
					Node->bOverrideFunction = true;
				});
			}
			if (Kind == TEXT("boundevent"))
			{
				FObjectProperty* Component = FindFProperty<FObjectProperty>(BP->SkeletonGeneratedClass, FName(*J->GetStringField(TEXT("widget"))));
				if (!Component)
				{
					Fail(FString::Printf(TEXT("%s: widget variable %s not found"), *Where, *J->GetStringField(TEXT("widget"))));
					return nullptr;
				}
				FMulticastDelegateProperty* Delegate = FindFProperty<FMulticastDelegateProperty>(Component->PropertyClass, FName(*Name));
				if (!Delegate)
				{
					Fail(FString::Printf(TEXT("%s: delegate %s not found"), *Where, *Name));
					return nullptr;
				}
				return Spawn<UK2Node_ComponentBoundEvent>([&](UK2Node_ComponentBoundEvent* Node)
				{
					Node->InitializeComponentBoundEventParams(Component, Delegate);
				});
			}
			if (Kind == TEXT("call"))
			{
				FString Left, Right;
				if (!J->GetStringField(TEXT("fn")).Split(TEXT(":"), &Left, &Right))
				{
					// Function of this Blueprint.
					const FString Self = J->GetStringField(TEXT("fn"));
					return Spawn<UK2Node_CallFunction>([&](UK2Node_CallFunction* Node)
					{
						Node->FunctionReference.SetSelfMember(FName(*Self));
					});
				}
				UClass* Class = FindClassByPath(Left);
				if (!Class) { return nullptr; }
				UFunction* Function = Class->FindFunctionByName(FName(*Right));
				if (!Function)
				{
					Fail(FString::Printf(TEXT("%s: function %s not found on %s"), *Where, *Right, *Left));
					return nullptr;
				}
				return Spawn<UK2Node_CallFunction>([&](UK2Node_CallFunction* Node)
				{
					Node->SetFromFunction(Function);
				});
			}
			if (Kind == TEXT("get") || Kind == TEXT("set"))
			{
				const FString Var = J->GetStringField(TEXT("var"));
				UClass* Class = ClassPath.IsEmpty() ? nullptr : FindClassByPath(ClassPath);
				if (!ClassPath.IsEmpty() && !Class) { return nullptr; }
				auto Init = [&](UK2Node_Variable* Node)
				{
					if (Class) { Node->VariableReference.SetExternalMember(FName(*Var), Class); }
					else { Node->VariableReference.SetSelfMember(FName(*Var)); }
				};
				if (Kind == TEXT("get"))
				{
					return Spawn<UK2Node_VariableGet>([&](UK2Node_VariableGet* Node) { Init(Node); });
				}
				return Spawn<UK2Node_VariableSet>([&](UK2Node_VariableSet* Node) { Init(Node); });
			}
			if (Kind == TEXT("branch"))
			{
				return Spawn<UK2Node_IfThenElse>([](UK2Node_IfThenElse*) {});
			}
			if (Kind == TEXT("self"))
			{
				return Spawn<UK2Node_Self>([](UK2Node_Self*) {});
			}
			if (Kind == TEXT("cast"))
			{
				UClass* Class = FindClassByPath(ClassPath);
				if (!Class) { return nullptr; }
				return Spawn<UK2Node_DynamicCast>([&](UK2Node_DynamicCast* Node)
				{
					Node->TargetType = Class;
					Node->SetPurity(false);
				});
			}
			if (Kind == TEXT("classcast"))
			{
				UClass* Class = FindClassByPath(ClassPath);
				if (!Class) { return nullptr; }
				return Spawn<UK2Node_ClassDynamicCast>([&](UK2Node_ClassDynamicCast* Node)
				{
					Node->TargetType = Class;
					Node->SetPurity(false);
				});
			}
			if (Kind == TEXT("seq"))
			{
				UK2Node_ExecutionSequence* Node = Spawn<UK2Node_ExecutionSequence>([](UK2Node_ExecutionSequence*) {});
				for (int32 Index = 2; Index < (int32)J->GetNumberField(TEXT("n")); ++Index)
				{
					Node->AddInputPin();
				}
				return Node;
			}
			if (Kind == TEXT("makearray"))
			{
				return Spawn<UK2Node_MakeArray>([&](UK2Node_MakeArray* Node)
				{
					Node->NumInputs = (int32)J->GetNumberField(TEXT("n"));
				});
			}
			if (Kind == TEXT("macro"))
			{
				UBlueprint* Macros = LoadObject<UBlueprint>(nullptr, TEXT("/Engine/EditorBlueprintResources/StandardMacros.StandardMacros"));
				UEdGraph* MacroGraph = nullptr;
				if (Macros)
				{
					for (UEdGraph* Candidate : Macros->MacroGraphs)
					{
						if (Candidate->GetName() == Name) { MacroGraph = Candidate; }
					}
				}
				if (!MacroGraph)
				{
					Fail(FString::Printf(TEXT("%s: macro %s not found"), *Where, *Name));
					return nullptr;
				}
				return Spawn<UK2Node_MacroInstance>([&](UK2Node_MacroInstance* Node)
				{
					Node->SetMacroGraph(MacroGraph);
				});
			}
			Fail(FString::Printf(TEXT("%s: unknown node kind %s"), *Where, *Kind));
			return nullptr;
		}

		UEdGraphPin* FindPin(const FString& Ref)
		{
			FString NodeId, PinName;
			if (!Ref.Split(TEXT("."), &NodeId, &PinName))
			{
				Fail(FString::Printf(TEXT("%s: bad pin reference %s"), *Where, *Ref));
				return nullptr;
			}
			UEdGraphNode** Found = Nodes.Find(NodeId);
			if (!Found || !*Found)
			{
				Fail(FString::Printf(TEXT("%s: node %s not found"), *Where, *NodeId));
				return nullptr;
			}
			UEdGraphPin* Pin = nullptr;
			if (PinName == TEXT("$cast"))
			{
				if (UK2Node_DynamicCast* CastNode = Cast<UK2Node_DynamicCast>(*Found)) { Pin = CastNode->GetCastResultPin(); }
			}
			else
			{
				Pin = (*Found)->FindPin(FName(*PinName));
			}
			if (!Pin)
			{
				FString Available;
				for (UEdGraphPin* Each : (*Found)->Pins) { Available += Each->PinName.ToString() + TEXT(" "); }
				Fail(FString::Printf(TEXT("%s: pin %s not found. Pins: %s"), *Where, *Ref, *Available));
			}
			return Pin;
		}

		void Build(const FJson& J)
		{
			Schema = GetDefault<UEdGraphSchema_K2>();
			if (UK2Node_FunctionEntry* Entry = FindEntry(Graph)) { Nodes.Add(TEXT("entry"), Entry); }
			if (UK2Node_FunctionResult* Result = FindResult(Graph)) { Nodes.Add(TEXT("result"), Result); }

			int32 Column = 0;
			const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
			if (J->TryGetArrayField(TEXT("nodes"), List))
			{
				for (const TSharedPtr<FJsonValue>& Value : *List)
				{
					const FJson NodeJson = Value->AsObject();
					const FString Id = NodeJson->GetStringField(TEXT("id"));
					UEdGraphNode* Node = MakeNode(NodeJson);
					if (!Node) { continue; }
					Node->NodePosX = 300 * (Column % 8);
					Node->NodePosY = 220 * (Column / 8);
					++Column;
					Nodes.Add(Id, Node);
				}
			}
			// Defaults first: class pins decide the type of output pins.
			const FJson* Defaults = nullptr;
			if (J->TryGetObjectField(TEXT("defaults"), Defaults))
			{
				for (const auto& Entry : (*Defaults)->Values)
				{
					UEdGraphPin* Pin = FindPin(Entry.Key);
					if (!Pin) { continue; }
					const FString Text = Entry.Value->AsString();
					const FName Category = Pin->PinType.PinCategory;
					if (Category == UEdGraphSchema_K2::PC_Object || Category == UEdGraphSchema_K2::PC_Class || Category == UEdGraphSchema_K2::PC_Interface)
					{
						UObject* Object = LoadObject<UObject>(nullptr, *Text);
						if (!Object) { Fail(FString::Printf(TEXT("%s: default object %s not found"), *Where, *Text)); continue; }
						Schema->TrySetDefaultObject(*Pin, Object);
					}
					else if (Category == UEdGraphSchema_K2::PC_Text)
					{
						Schema->TrySetDefaultText(*Pin, FText::FromString(Text));
					}
					else
					{
						Schema->TrySetDefaultValue(*Pin, Text);
					}
				}
			}
			if (J->TryGetArrayField(TEXT("links"), List))
			{
				for (const TSharedPtr<FJsonValue>& Value : *List)
				{
					const TArray<TSharedPtr<FJsonValue>>& Pair = Value->AsArray();
					UEdGraphPin* A = FindPin(Pair[0]->AsString());
					UEdGraphPin* B = FindPin(Pair[1]->AsString());
					if (A && B && !A->LinkedTo.Contains(B) && !Schema->TryCreateConnection(A, B))
					{
						Fail(FString::Printf(TEXT("%s: cannot connect %s -> %s"), *Where, *Pair[0]->AsString(), *Pair[1]->AsString()));
					}
				}
			}
		}
	};

	void BuildGraphs(UBlueprint* BP, const FJson& J)
	{
		const FJson* Graphs = nullptr;
		if (!J->TryGetObjectField(TEXT("graphs"), Graphs))
		{
			return;
		}
		for (const auto& Pair : (*Graphs)->Values)
		{
			UEdGraph* Graph = FindGraph(BP, Pair.Key);
			if (!Graph)
			{
				Fail(FString::Printf(TEXT("Graph %s not found in %s"), *Pair.Key, *BP->GetName()));
				continue;
			}
			if (Pair.Key == TEXT("EventGraph"))
			{
				// Drop the placeholder nodes the editor adds to a new Blueprint.
				TArray<UEdGraphNode*> Old = Graph->Nodes;
				for (UEdGraphNode* Node : Old) { Graph->RemoveNode(Node); }
			}
			FGraphBuilder Builder;
			Builder.BP = BP;
			Builder.Graph = Graph;
			Builder.Where = BP->GetName() + TEXT(".") + Pair.Key;
			Builder.Build(Pair.Value->AsObject());
		}
	}

	/** Runs Blueprint logic in a throwaway game world; can render the world to a PNG. Writes no assets. */
	struct FWorldTest
	{
		UWorld* World = nullptr;
		TMap<FString, UObject*> Objects;

		UObject* Find(const FString& Id)
		{
			UObject** Found = Objects.Find(Id);
			if (!Found || !*Found)
			{
				Fail(FString::Printf(TEXT("worldtest: object %s not found"), *Id));
				return nullptr;
			}
			return *Found;
		}

		/** The object itself, or its first component of the class in "component". */
		UObject* Target(const FJson& J, const FString& Id)
		{
			UObject* Object = Find(Id);
			FString ComponentClass;
			if (Object && J->TryGetStringField(TEXT("component"), ComponentClass))
			{
				AActor* Actor = Cast<AActor>(Object);
				UClass* Class = FindClassByPath(ComponentClass);
				Object = (Actor && Class) ? Actor->GetComponentByClass(Class) : nullptr;
				if (!Object) { Fail(FString::Printf(TEXT("worldtest: %s has no %s"), *Id, *ComponentClass)); }
			}
			return Object;
		}

		static FVector Vec(const FJson& J, const TCHAR* Field, const FVector& Default)
		{
			const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
			if (!J->TryGetArrayField(Field, Values) || Values->Num() != 3) { return Default; }
			return FVector((*Values)[0]->AsNumber(), (*Values)[1]->AsNumber(), (*Values)[2]->AsNumber());
		}

		void Step(const FJson& J)
		{
			FString Value;
			if (J->TryGetStringField(TEXT("spawn"), Value))
			{
				UClass* Class = FindClassByPath(Value);
				if (!Class) { return; }
				const FVector Rot = Vec(J, TEXT("rot"), FVector::ZeroVector);
				FActorSpawnParameters Params;
				Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				AActor* Actor = World->SpawnActor<AActor>(Class, Vec(J, TEXT("loc"), FVector::ZeroVector), FRotator(Rot.X, Rot.Y, Rot.Z), Params);
				if (!Actor)
				{
					Fail(FString::Printf(TEXT("worldtest: could not spawn %s"), *Value));
					return;
				}
				// Set the rotation again: spawning combines it with the class's own root rotation.
				// Only movable components can be moved once play has begun.
				if (USceneComponent* Root = Actor->GetRootComponent()) { Root->SetMobility(EComponentMobility::Movable); }
				Actor->SetActorRotation(FRotator(Rot.X, Rot.Y, Rot.Z));
				Actor->SetActorScale3D(Vec(J, TEXT("scale"), FVector(1.f)));
				Objects.Add(J->GetStringField(TEXT("as")), Actor);
			}
			else if (J->TryGetStringField(TEXT("comp"), Value))
			{
				// Component of an actor, by name.
				AActor* Actor = Cast<AActor>(Find(Value));
				UActorComponent* Match = nullptr;
				if (Actor)
				{
					for (UActorComponent* Component : Actor->GetComponents())
					{
						if (Component && Component->GetName() == J->GetStringField(TEXT("name"))) { Match = Component; }
					}
				}
				if (!Match) { Fail(FString::Printf(TEXT("worldtest: component %s not found"), *J->GetStringField(TEXT("name")))); return; }
				Objects.Add(J->GetStringField(TEXT("as")), Match);
			}
			else if (J->TryGetStringField(TEXT("addcomp"), Value))
			{
				AActor* Actor = Cast<AActor>(Find(Value));
				UClass* Class = FindClassByPath(J->GetStringField(TEXT("class")));
				if (!Actor || !Class) { return; }
				UActorComponent* Component = NewObject<UActorComponent>(Actor, Class);
				const FJson* Props = nullptr;
				if (J->TryGetObjectField(TEXT("props"), Props)) { ImportProps(Component, *Props); }
				if (USceneComponent* Scene = Cast<USceneComponent>(Component))
				{
					if (Actor->GetRootComponent()) { Scene->SetupAttachment(Actor->GetRootComponent()); }
					else { Actor->SetRootComponent(Scene); }
				}
				Actor->AddInstanceComponent(Component);
				Component->RegisterComponent();
				Objects.Add(J->GetStringField(TEXT("as")), Component);
			}
			else if (J->TryGetStringField(TEXT("props"), Value))
			{
				UObject* Object = Target(J, Value);
				if (!Object) { return; }
				ImportProps(Object, J->GetObjectField(TEXT("values")));
				if (UActorComponent* Component = Cast<UActorComponent>(Object)) { Component->ReregisterComponent(); }
			}
			else if (J->TryGetStringField(TEXT("call"), Value))
			{
				FString Id, FunctionName;
				Value.Split(TEXT("."), &Id, &FunctionName);
				UObject* Object = Find(Id);
				if (!Object) { return; }
				UFunction* Function = Object->FindFunction(FName(*FunctionName));
				if (!Function)
				{
					// Generated event names carry a counter; allow a part of the name.
					for (TFieldIterator<UFunction> It(Object->GetClass()); It && !Function; ++It)
					{
						if (It->GetName().Contains(FunctionName)) { Function = *It; }
					}
				}
				if (!Function)
				{
					Fail(FString::Printf(TEXT("worldtest: function %s not found"), *Value));
					return;
				}
				// InitializeStruct covers parameters and locals, so the buffer must hold PropertiesSize.
				const int32 BufferSize = FMath::Max<int32>(Function->PropertiesSize, 1);
				uint8* Buffer = (uint8*)FMemory_Alloca(BufferSize);
				FMemory::Memzero(Buffer, BufferSize);
				Function->InitializeStruct(Buffer);
				const FJson* Args = nullptr;
				if (J->TryGetObjectField(TEXT("args"), Args))
				{
					for (const auto& Pair : (*Args)->Values)
					{
						FProperty* Param = Function->FindPropertyByName(FName(*Pair.Key));
						if (!Param)
						{
							Fail(FString::Printf(TEXT("worldtest: parameter %s not found"), *Pair.Key));
							continue;
						}
						const FString Text = Pair.Value->AsString();
						void* ValuePtr = Param->ContainerPtrToValuePtr<void>(Buffer);
						if (Text.StartsWith(TEXT("@")))
						{
							CastFieldChecked<FObjectProperty>(Param)->SetObjectPropertyValue(ValuePtr, Find(Text.Mid(1)));
						}
						else
						{
							Param->ImportText(*Text, ValuePtr, PPF_None, nullptr);
						}
					}
				}
				Object->ProcessEvent(Function, Buffer);
				Function->DestroyStruct(Buffer);
			}
			else if (J->TryGetStringField(TEXT("get"), Value))
			{
				FString Id, PropertyName;
				Value.Split(TEXT("."), &Id, &PropertyName);
				UObject* Object = Find(Id);
				FObjectProperty* Property = Object ? FindFProperty<FObjectProperty>(Object->GetClass(), FName(*PropertyName)) : nullptr;
				if (!Property)
				{
					Fail(FString::Printf(TEXT("worldtest: property %s not found"), *Value));
					return;
				}
				Objects.Add(J->GetStringField(TEXT("as")), Property->GetObjectPropertyValue_InContainer(Object));
			}
			else if (J->TryGetStringField(TEXT("find"), Value))
			{
				// First actor of a class in the world.
				UClass* Class = FindClassByPath(Value);
				AActor* Actor = nullptr;
				for (TActorIterator<AActor> It(World, Class); It && !Actor; ++It) { Actor = *It; }
				UE_LOG(LogBPForge, Display, TEXT("TEST find %s -> %s"), *Value, Actor ? *Actor->GetName() : TEXT("none"));
				Objects.Add(J->GetStringField(TEXT("as")), Actor);
			}
			else if (J->TryGetStringField(TEXT("print"), Value))
			{
				UObject* Object = Target(J, Value);
				if (!Object) { return; }
				for (const TSharedPtr<FJsonValue>& Name : J->GetArrayField(TEXT("fields")))
				{
					FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Name->AsString()));
					FString Text = TEXT("<missing>");
					if (Property)
					{
						Text.Reset();
						Property->ExportTextItem(Text, Property->ContainerPtrToValuePtr<void>(Object), nullptr, Object, PPF_None);
					}
					UE_LOG(LogBPForge, Display, TEXT("TEST %s.%s = %s"), *Value, *Name->AsString(), *Text);
				}
			}
			else if (J->TryGetStringField(TEXT("destroy"), Value))
			{
				AActor* Actor = Cast<AActor>(Find(Value));
				if (Actor && !World->DestroyActor(Actor, true, true))
				{
					Fail(FString::Printf(TEXT("worldtest: could not destroy %s"), *Value));
				}
				Objects.Remove(Value);
			}
			else if (J->TryGetStringField(TEXT("cvar"), Value))
			{
				IConsoleVariable* Variable = IConsoleManager::Get().FindConsoleVariable(*Value);
				UE_LOG(LogBPForge, Display, TEXT("TEST cvar %s = %s"), *Value, Variable ? *Variable->GetString() : TEXT("<missing>"));
			}
			else if (J->TryGetStringField(TEXT("capture"), Value))
			{
				Capture(J, Value);
			}
			else
			{
				Fail(TEXT("worldtest: unknown step"));
			}
		}

		/** Renders the world from a camera to a PNG (tonemapped, fixed exposure). */
		void Capture(const FJson& J, const FString& File)
		{
			const FVector Rot = Vec(J, TEXT("rot"), FVector::ZeroVector);
			ASceneCapture2D* Camera = World->SpawnActor<ASceneCapture2D>(Vec(J, TEXT("loc"), FVector::ZeroVector), FRotator(Rot.X, Rot.Y, Rot.Z));
			USceneCaptureComponent2D* Component = Camera->GetCaptureComponent2D();
			UTextureRenderTarget2D* RenderTarget = NewObject<UTextureRenderTarget2D>(GetTransientPackage());
			RenderTarget->RenderTargetFormat = RTF_RGBA8;
			RenderTarget->TargetGamma = 2.2f; // store display values, not linear ones
			RenderTarget->InitAutoFormat(1280, 720);
			RenderTarget->UpdateResourceImmediate(true);
			Component->TextureTarget = RenderTarget;
			Component->CaptureSource = SCS_FinalColorLDR;
			Component->FOVAngle = 90.f;
			Component->bCaptureEveryFrame = false;
			Component->bCaptureOnMovement = false;
			Component->bAlwaysPersistRenderingState = true;
			FPostProcessSettings& Post = Component->PostProcessSettings;
			Post.bOverride_AutoExposureMinBrightness = true;
			Post.bOverride_AutoExposureMaxBrightness = true;
			Post.AutoExposureMinBrightness = 1.f;
			Post.AutoExposureMaxBrightness = 1.f;
			Post.bOverride_AutoExposureBias = true;
			double Exposure = 0.0;
			J->TryGetNumberField(TEXT("exposure"), Exposure); // stops; raise to look into dark scenes
			Post.AutoExposureBias = (float)Exposure;
			Post.bOverride_AutoExposureMethod = true;
			Post.AutoExposureMethod = AEM_Histogram;
			Post.bOverride_BloomIntensity = true;
			Post.BloomIntensity = 0.4f;
			Post.bOverride_VignetteIntensity = true;
			Post.VignetteIntensity = 0.f;
			Component->PostProcessBlendWeight = 1.f;

			// Several frames so shaders finish and temporal history (volumetric fog, exposure) settles.
			for (int32 Frame = 0; Frame < 24; ++Frame)
			{
				if (GShaderCompilingManager && GShaderCompilingManager->IsCompiling())
				{
					GShaderCompilingManager->FinishAllCompilation();
					Frame = 0;
				}
				World->Tick(LEVELTICK_All, 1.f / 30.f);
				World->SendAllEndOfFrameUpdates();
				Component->CaptureScene();
				FlushRenderingCommands();
			}
			FArchive* Writer = IFileManager::Get().CreateFileWriter(*File);
			if (!Writer || !FImageUtils::ExportRenderTarget2DAsPNG(RenderTarget, *Writer))
			{
				Fail(FString::Printf(TEXT("worldtest: could not write %s"), *File));
			}
			delete Writer;
			UE_LOG(LogBPForge, Display, TEXT("TEST captured %s"), *File);
			Camera->Destroy();
		}

		void Run(const FJson& J)
		{
			World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("BPForgeTestWorld"));
			FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
			Context.SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			// No game mode here, so start play by hand: actors spawned from now on get BeginPlay.
			World->GetWorldSettings()->NotifyBeginPlay();
			for (const TSharedPtr<FJsonValue>& Value : J->GetArrayField(TEXT("steps")))
			{
				Step(Value->AsObject());
				if (GFailed) { break; }
			}
			GEngine->DestroyWorldContext(World);
			World->DestroyWorld(false);
		}
	};

	TMap<FString, UBlueprint*> GBuilt;

	void BuildAsset(const FJson& J)
	{
		const FString Kind = J->GetStringField(TEXT("kind"));
		if (Kind == TEXT("worldtest"))
		{
			FWorldTest Test;
			Test.Run(J);
			return;
		}
		const FString Path = J->GetStringField(TEXT("path"));
		const FString AssetName = FPackageName::GetLongPackageAssetName(Path);
		UE_LOG(LogBPForge, Display, TEXT("Building %s (%s)"), *Path, *Kind);

		if (Kind == TEXT("graphs"))
		{
			UBlueprint** Found = GBuilt.Find(Path);
			if (!Found)
			{
				Fail(FString::Printf(TEXT("graphs: %s was not declared earlier"), *Path));
				return;
			}
			BuildGraphs(*Found, J);
			if (!GFailed && Compile(*Found)) { Save(*Found); }
			return;
		}

		if (Kind == TEXT("dump"))
		{
			// Read-only: log the function signatures of a class.
			if (UClass* Class = FindClassByPath(Path))
			{
				for (TFieldIterator<UFunction> It(Class, EFieldIteratorFlags::ExcludeSuper); It; ++It)
				{
					FString Line = It->GetName() + TEXT("(");
					for (TFieldIterator<FProperty> Param(*It); Param && Param->HasAnyPropertyFlags(CPF_Parm); ++Param)
					{
						Line += FString::Printf(TEXT("%s%s %s; "), Param->HasAnyPropertyFlags(CPF_OutParm) ? TEXT("out ") : TEXT(""),
							*Param->GetCPPType(), *Param->GetName());
					}
					UE_LOG(LogBPForge, Display, TEXT("  %s)"), *Line);
				}
			}
			return;
		}

		if (Kind == TEXT("functions"))
		{
			UBlueprint** Found = GBuilt.Find(Path);
			if (!Found)
			{
				Fail(FString::Printf(TEXT("functions: %s was not declared earlier"), *Path));
				return;
			}
			for (const TSharedPtr<FJsonValue>& Value : J->GetArrayField(TEXT("functions")))
			{
				AddFunction(*Found, Value->AsObject());
			}
			FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(*Found);
			if (!GFailed && Compile(*Found)) { Save(*Found); }
			return;
		}

		UPackage* Package = CreatePackage(*Path);
		UBlueprint* BP = nullptr;
		if (Kind == TEXT("interface"))
		{
			BP = FKismetEditorUtilities::CreateBlueprint(UInterface::StaticClass(), Package, FName(*AssetName), BPTYPE_Interface,
				UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
		}
		else
		{
			UClass* Parent = FindClassByPath(J->GetStringField(TEXT("parent")));
			if (!Parent) { return; }
			if (Kind == TEXT("widget"))
			{
				BP = FKismetEditorUtilities::CreateBlueprint(Parent, Package, FName(*AssetName), BPTYPE_Normal,
					UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass());
			}
			else
			{
				BP = FKismetEditorUtilities::CreateBlueprint(Parent, Package, FName(*AssetName), BPTYPE_Normal,
					UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
			}
		}
		if (!BP)
		{
			Fail(FString::Printf(TEXT("Could not create %s"), *Path));
			return;
		}
		FAssetRegistryModule::AssetCreated(BP);
		GBuilt.Add(Path, BP);

		const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
		if (J->TryGetArrayField(TEXT("interfaces"), List))
		{
			for (const TSharedPtr<FJsonValue>& Value : *List)
			{
				UClass* Interface = FindClassByPath(Value->AsString());
				if (Interface && !FBlueprintEditorUtils::ImplementNewInterface(BP, Interface->GetFName()))
				{
					Fail(FString::Printf(TEXT("Could not implement %s"), *Value->AsString()));
				}
			}
		}
		if (J->TryGetArrayField(TEXT("variables"), List))
		{
			for (const TSharedPtr<FJsonValue>& Value : *List)
			{
				const FJson Var = Value->AsObject();
				FEdGraphPinType PinType;
				if (!MakePinType(Var, PinType)) { continue; }
				FString Default;
				Var->TryGetStringField(TEXT("default"), Default);
				if (!FBlueprintEditorUtils::AddMemberVariable(BP, FName(*Var->GetStringField(TEXT("name"))), PinType, Default))
				{
					Fail(FString::Printf(TEXT("Could not add variable %s"), *Var->GetStringField(TEXT("name"))));
				}
			}
		}
		if (J->TryGetArrayField(TEXT("functions"), List))
		{
			for (const TSharedPtr<FJsonValue>& Value : *List)
			{
				AddFunction(BP, Value->AsObject());
			}
		}
		if (J->TryGetArrayField(TEXT("components"), List) && BP->SimpleConstructionScript)
		{
			for (const TSharedPtr<FJsonValue>& Value : *List)
			{
				const FJson Comp = Value->AsObject();
				UClass* CompClass = FindClassByPath(Comp->GetStringField(TEXT("class")));
				if (!CompClass) { continue; }
				USCS_Node* Node = BP->SimpleConstructionScript->CreateNode(CompClass, FName(*Comp->GetStringField(TEXT("name"))));
				BP->SimpleConstructionScript->AddNode(Node);
				const FJson* CompProps = nullptr;
				if (Comp->TryGetObjectField(TEXT("props"), CompProps))
				{
					ImportProps(Node->ComponentTemplate, *CompProps);
				}
			}
		}
		const FJson* Tree = nullptr;
		if (Kind == TEXT("widget") && J->TryGetObjectField(TEXT("tree"), Tree))
		{
			BuildWidget(CastChecked<UWidgetBlueprint>(BP), *Tree, nullptr);
		}
		FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
		if (GFailed || !Compile(BP)) { return; }

		BuildGraphs(BP, J);
		if (GFailed || !Compile(BP)) { return; }
		const FJson* ClassDefaults = nullptr;
		if (J->TryGetObjectField(TEXT("class_defaults"), ClassDefaults))
		{
			ImportProps(BP->GeneratedClass->GetDefaultObject(), *ClassDefaults);
		}
		bool bTransient = false;
		J->TryGetBoolField(TEXT("transient"), bTransient);
		if (!GFailed && !bTransient) { Save(BP); }
	}
}

int32 UBPForgeCommandlet::Main(const FString& Params)
{
	FString SpecPath;
	if (!FParse::Value(*Params, TEXT("Spec="), SpecPath))
	{
		UE_LOG(LogBPForge, Error, TEXT("Usage: -run=BPForge -Spec=<file.json>"));
		return 1;
	}
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *SpecPath))
	{
		UE_LOG(LogBPForge, Error, TEXT("Cannot read %s"), *SpecPath);
		return 1;
	}
	FJson Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogBPForge, Error, TEXT("Cannot parse %s"), *SpecPath);
		return 1;
	}
	for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("assets")))
	{
		BuildAsset(Value->AsObject());
		if (GFailed)
		{
			UE_LOG(LogBPForge, Error, TEXT("BPForge stopped: errors above."));
			return 1;
		}
	}
	UE_LOG(LogBPForge, Display, TEXT("BPForge finished: %d assets."), GBuilt.Num());
	return 0;
}
