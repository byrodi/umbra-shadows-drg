#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"
#include "BPForgeCommandlet.generated.h"

/** Builds Blueprint assets from a JSON spec. Usage: -run=BPForge -Spec=<file.json> */
UCLASS()
class UBPForgeCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	virtual int32 Main(const FString& Params) override;
};
