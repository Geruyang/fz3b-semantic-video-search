[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot 'source-pack')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Copy-Checked([string]$Source,[string]$Destination,[string]$Expected) {
    if (!(Test-Path -LiteralPath $Source -PathType Leaf)) { throw "missing source $Source" }
    if ((Sha $Source) -ne $Expected) { throw "source SHA mismatch $Source" }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    if ((Sha $Destination) -ne $Expected) { throw "snapshot SHA mismatch $Destination" }
}

$accel = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$candidate = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\candidate'))
$out = [IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $out) { throw "OutputDir must be new: $out" }
New-Item -ItemType Directory -Path $out -Force | Out-Null

$files = [ordered]@{
    'cnn_pipeline_v10.cpp'       = @((Join-Path $candidate 'cnn_pipeline_v10_a0005.cpp'),'e2f89426cfecb9b4f4055e3065232841dd0994d2997cbd7fb2591b4895b9c85f')
    'cnn_pipeline_v10.hpp'       = @((Join-Path $candidate 'cnn_pipeline_v10_a0005.hpp'),'2383f6f6ea9d7d4cfaedebbe2810e05bdb68d452c09f170e4215ad9c180e0d93')
    'cnn_pipeline_v10_a0005.hpp' = @((Join-Path $candidate 'cnn_pipeline_v10_a0005.hpp'),'2383f6f6ea9d7d4cfaedebbe2810e05bdb68d452c09f170e4215ad9c180e0d93')
    'cnn_v10_pointwise.hpp'      = @((Join-Path $candidate 'cnn_v10_pointwise_a0005.hpp'),'a5ca1175d671f7bd87babe1fcb8a1ecba955e559aea7ea0c799f5f031b06be05')
    'cnn_v10_pointwise_a0005.hpp'= @((Join-Path $candidate 'cnn_v10_pointwise_a0005.hpp'),'a5ca1175d671f7bd87babe1fcb8a1ecba955e559aea7ea0c799f5f031b06be05')
    'cnn_v10_identity.hpp'       = @((Join-Path $candidate 'cnn_v10_identity_a0005.hpp'),'042efb1a098d7dd2c2d49791fd285162b7bc95fed0e0c78f62db32092d8af93d')
    'cnn_v10_identity_a0005.hpp' = @((Join-Path $candidate 'cnn_v10_identity_a0005.hpp'),'042efb1a098d7dd2c2d49791fd285162b7bc95fed0e0c78f62db32092d8af93d')
    'cnn_v10_storage_contract.hpp'= @((Join-Path $candidate 'cnn_v10_storage_contract.hpp'),'a2634442d410fef0106ce44e6d6a8012786d24f3b0c7af3fc651f8b877fbd32d')
    'cnn_v10_storage_helpers.hpp'= @((Join-Path $candidate 'cnn_v10_storage_helpers.hpp'),'3c1ad9a3a8dc0f2306ee533bf347b0b2768adbcf3ea276bde1a9d749aeb78d05')
    'cnn_v10_pw2_storage.hpp'    = @((Join-Path $candidate 'cnn_v10_pw2_storage.hpp'),'94667c1df475de9ced92d4af608deb0d001c2c79481c1ac78ba6fc97dc0302dd')
    'candidate-contract.json'    = @((Join-Path $candidate 'candidate-contract.json'),'a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d')
    'candidate-source-manifest.json'= @((Join-Path $candidate 'source-manifest.json'),'f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593')
    'cnn_v10_param_broker.hpp'   = @((Join-Path $accel 'cnn_v10_param_broker.hpp'),'af014cdf5fca5fcc1a4b8ec285a1f0e330cf7ea9af3167b4d09c1eab0d6ece8a')
    'cnn_v10_arithmetic.hpp'     = @((Join-Path $accel 'cnn_v10_arithmetic.hpp'),'f0f4f9a0109228b278e5d6395bca77381f8cdf004c322979292c491f387ca6c1')
    'cnn_v10_gelu.hpp'           = @((Join-Path $accel 'cnn_v10_gelu.hpp'),'d265b00627ebbe053a8c7798f1c3a3a98eb4dcae679ba6e24c4fe7c4fcd81639')
    'cnn_v10_ddr.hpp'            = @((Join-Path $accel 'cnn_v10_ddr.hpp'),'373e616f16c4e293a3507ddd6f2f5f421ae45ee6b7a22c6b47df40909b61f328')
    'cnn_v10_scale_service.hpp'  = @((Join-Path $accel 'cnn_v10_scale_service.hpp'),'12c6a2c6d76bb78fad3cc3bcc75cdb5cdbeb990a0fece454e85c3607748bdf5d')
    'cnn_v10_n1.hpp'             = @((Join-Path $accel 'cnn_v10_n1.hpp'),'444afa338b1e975a792fcb1adcdbb43d312caedadfbc20897fa057b66f8be916')
    'cnn_v10_gelu_segmented.hpp' = @((Join-Path $accel 'cnn_v10_gelu_segmented.hpp'),'0846e03a7dcdfd416f457b3138bb9af4989c551a7bfbbd1ad78f20dead3d0cba')
    'cnn_v10_pw_dsp.hpp'         = @((Join-Path $accel 'cnn_v10_pw_dsp.hpp'),'26994f7d03874986c4e3330604024ad4b538205915bb8a8d9c03e1c8f430bff5')
    'cnn_v10_pw_dsp_model.cpp'   = @((Join-Path $accel 'cnn_v10_pw_dsp_model.cpp'),'e9de73d26c5ae3513b3671f3610b2bf8d58db4681e0cd74a2e1457115a87a8f8')
    'cnn_v10_pw_dsp16.json'      = @((Join-Path $accel 'cnn_v10_pw_dsp16.json'),'46f37dd6c05fa744de0573548dfb4d6bac65e3fb7f8b6c952715fa064ae98b23')
    'cnn_v10_pw_dsp16.v'         = @((Join-Path $accel 'cnn_v10_pw_dsp16.v'),'112e118f23682816e5be4741433b93f940a269548517de0de639f71b9a9e10b9')
    'tb_cnn_v10_pw_dsp16.sv'     = @((Join-Path $accel 'tb_cnn_v10_pw_dsp16.sv'),'3cbc7bccc0c77de98386171a486765f43743b6450ee6e7750ae797655a18bbe6')
    'cnn_pipeline_v10_host_tb.cpp'= @((Join-Path $accel 'cnn_pipeline_v10_host_tb.cpp'),'c95e5e5b82ba6591733b0b017d7bf32634038f4634958fa30ce2e88c7d45791c')
}
foreach ($name in $files.Keys) { Copy-Checked $files[$name][0] (Join-Path $out $name) $files[$name][1] }

foreach ($helper in @('task_tool_error_mode.ps1','task_tool_memory.ps1')) {
    Copy-Item -LiteralPath (Join-Path $accel $helper) -Destination (Join-Path $out $helper) -Force
}

$nativeSource = Join-Path $accel 'run_cnn_pipeline_v10_native_csim.ps1'
$nativeText = Get-Content -LiteralPath $nativeSource -Raw
$nativeText = $nativeText.Replace("0x000A0004u", "0x000A0005u").Replace('sw10[.]4','sw10[.]5')
$nativeText = $nativeText.Replace("abi='0x000A0004';software='sw10.4'", "abi='0x000A0005';software='sw10.5'")
$nativeText = $nativeText.Replace("if(`$pointwiseText-notmatch'#define\s+CNN_V10_PW2_COLUMNS_DEPTH\s+1024'){throw 'PW2 columns depth must remain 1024'}", "if(`$pointwiseText-notmatch'#define\s+CNN_V10_PW2_COLUMNS_DEPTH\s+1024'){throw 'PW2 columns depth must remain 1024'}; if(`$pointwiseText-notmatch'typedef\s+(?:::)?cnn_v10_candidate::Pw2StoredColumn\s+Pw2StoredColumn'){throw 'A0005 signed40 PW2 storage binding missing'}; if(`$identityText-notmatch'kGuardCapabilities\s*=\s*0x00000fffu' -or `$identityText-notmatch'kPw2Signed40ApprovedParamsCapability\s*=\s*0x00000800u'){throw 'A0005 capability identity missing'}")
$nativeText | Set-Content -LiteralPath (Join-Path $out 'run_cnn_pipeline_v10_a0005_native_csim.ps1') -Encoding utf8

$hlsTemplate = Join-Path $PSScriptRoot 'run_cnn_pipeline_v10_a0005_hls_synth.ps1'
Copy-Checked $hlsTemplate (Join-Path $out 'run_cnn_pipeline_v10_a0005_hls_synth.ps1') `
    '00d3b488b272e39be5b9dfb10c18c19aa558c1d1227ccd5547221eb260057626'

$inventory = [ordered]@{}
foreach ($name in $files.Keys) { $inventory[$name] = Sha (Join-Path $out $name) }
$inventory['native_runner'] = Sha (Join-Path $out 'run_cnn_pipeline_v10_a0005_native_csim.ps1')
$inventory['hls_runner'] = Sha (Join-Path $out 'run_cnn_pipeline_v10_a0005_hls_synth.ps1')
[ordered]@{
    schema='cnn-v10.5-a0005-full-source-pack-v1'
    candidate_source_manifest_sha256='f8714065c490506f5e08b1738c8fe121270db2c66da9eb42d9674907102e0593'
    candidate_contract_sha256='a65bdd2c50a5f1b5329350e22a67d9fb9ff4731c3517454ae524f667c5dc3f4d'
    software_ready_v3_sha256='ea6251ee897377a9831eba3de7cecbd5badcf9072680c68e2ae2fc0f61d7f733'
    files=$inventory
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'source-pack-manifest.json') -Encoding utf8

Write-Host "A0005_SOURCE_PACK_READY $out"
