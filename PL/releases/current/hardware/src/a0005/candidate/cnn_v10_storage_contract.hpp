#pragma once

#ifndef AP_INT_MAX_W
#define AP_INT_MAX_W 2048
#endif
#include <ap_int.h>

namespace cnn_v10_candidate {

static const unsigned kCoreIdentity = 0x465A5641u;  // "FZVA"
static const unsigned kAbiIdentity = 0x000A0005u;
static const char kSoftwareIdentity[] = "sw10.5";

static const unsigned kLegacyGuardCaps = 0x000007ffu;
static const unsigned kPw2Signed40ApprovedParamsCapability = 0x00000800u;
static const unsigned kGuardCaps =
    kLegacyGuardCaps | kPw2Signed40ApprovedParamsCapability;

static const unsigned kPw2StoredSignedBits = 40;
static const long long kPw2StoredMin = -549755813888LL;
static const long long kPw2StoredMax =  549755813887LL;
static const char kParameterCompatibilityObject[] =
    "parameter_compatibility.pw2_signed40_v1";
static const char kProofLayoutVersion[] = "cnn_v10_pw2_layout_v1";
static const char kBoundFormula[] = "abs(bias)+32768*sumabs(weight)";
static const unsigned kInputCodeAbsBound = 32768;
static const char kProofReceiptSha256[] =
    "9f3de6ffb18a9d1de54addbcc471f95f18c47acf86f31e051794d59e528b2676";
static const char kCombinedParameterManifestSha256[] =
    "4a32c9373e783ac572a5d3374b316181a4d52ae9a92ec45f8b13d763ef028690";
static const ap_uint<32> kCombinedParameterManifestWords[8] = {
    0x4a32c937u,0x3e783ac5u,0x72a5d337u,0x4b316181u,
    0xa4d52ae9u,0xa92ec45fu,0x8b13d763u,0xef028690u
};
static const char kApprovedRawParameterSha256[4][65] = {
    "1be71ba96c31cfb1a1734c0c3a4eb32bd2fd9f519d74f7827ae2385b604bd772",
    "2b217316c31ab2c2e5dbb7bd897a308ff07c67941607315af90fd46b7f824814",
    "8a9718b15e68d6857667d24c4d3c3c67201baaf2d3a560b657f27c358f9cd082",
    "f6ece07c73678835a6d25dd13b5ecafa7f106f03d279eea7b2b51a1898cc09ce"
};
static const long long kProfileMaxAbsBound[4] = {
    127754959201LL,230769820992LL,60088721889LL,35705743118LL
};
static const bool kSigned40StorageApplies[4] = {true,true,true,false};
static const char kNormalPw2WeightTileOrder[] = "normal_pw2_r_group_v1";
static const char kP3PwWeightTileOrder[] = "p3_pw_group_r_v1";

static_assert(kGuardCaps == 0x00000fffu,
              "A0005 capability identity must remain exact");
static_assert(kPw2StoredSignedBits == 40,
              "A0005 PW2 storage width must remain exact");

}  // namespace cnn_v10_candidate
