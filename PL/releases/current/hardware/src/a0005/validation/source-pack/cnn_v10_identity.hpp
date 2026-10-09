#pragma once

// Offline v10.5 candidate identity.  No deployed driver or default transport
// is changed by this file; packaging must bind these constants, the approved
// parameter set, the guard, and software together.
namespace cnn_v10 {

static const unsigned kCoreIdentity = 0x465A5641u;  // "FZVA"
static const unsigned kAbiIdentity = 0x000A0005u;
static const char kSoftwareIdentity[] = "sw10.5";
static const unsigned kGuardCapabilities = 0x00000fffu;
static const unsigned kPw2Signed40ApprovedParamsCapability = 0x00000800u;
static const char kCombinedParameterManifestSha256[] =
    "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690";

}  // namespace cnn_v10

