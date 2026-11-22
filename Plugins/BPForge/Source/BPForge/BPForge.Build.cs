using UnrealBuildTool;

public class BPForge : ModuleRules
{
	public BPForge(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PrivateDependencyModuleNames.AddRange(new string[] {
			"Core", "CoreUObject", "Engine", "UnrealEd", "BlueprintGraph", "Kismet", "KismetCompiler",
			"UMG", "UMGEditor", "Json", "AssetRegistry", "Slate", "SlateCore", "RenderCore", "RHI", "InputCore"
		});
	}
}
