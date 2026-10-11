
################################################################
# This is a generated script based on design: cnn_rtl_platform
#
# Though there are limitations about the generated script,
# the main purpose of this utility is to make learning
# IP Integrator Tcl commands easier.
################################################################

namespace eval _tcl {
proc get_script_folder {} {
   set script_path [file normalize [info script]]
   set script_folder [file dirname $script_path]
   return $script_folder
}
}
variable script_folder
set script_folder [_tcl::get_script_folder]

################################################################
# Check if script is running in correct Vivado version.
################################################################
set scripts_vivado_version 2026.1
set current_vivado_version [version -short]

if { [string first $scripts_vivado_version $current_vivado_version] == -1 } {
   puts ""
   if { [string compare $scripts_vivado_version $current_vivado_version] > 0 } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2042 -severity "ERROR" " This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Sourcing the script failed since it was created with a future version of Vivado."}

   } else {
     catch {common::send_gid_msg -ssname BD::TCL -id 2041 -severity "ERROR" "This script was generated using Vivado <$scripts_vivado_version> and is being run in <$current_vivado_version> of Vivado. Please run the script in Vivado <$scripts_vivado_version> then open the design in Vivado <$current_vivado_version>. Upgrade the design by running \"Tools => Report => Report IP Status...\", then run write_bd_tcl to create an updated script."}

   }

   return 1
}

################################################################
# START
################################################################

# To test this script, run the following commands from Vivado Tcl console:
# source cnn_rtl_platform_script.tcl


# The design that will be created by this Tcl script contains the following 
# module references:
# fzv10_ddr_guard_bd, fzv4_axi_hp0_monitor, ps8_axi_reset, cnn_v10_half2x_clock_tree

# Please add the sources of those modules before sourcing this Tcl script.

# If there is no project opened, this script will create a
# project, but make sure you do not have an existing project
# <./myproj/project_1.xpr> in the current working folder.

set list_projs [get_projects -quiet]
if { $list_projs eq "" } {
   create_project project_1 myproj -part xazu3eg-sfvc784-1-i
}


# CHANGE DESIGN NAME HERE
variable design_name
set design_name cnn_rtl_platform

# If you do not already have an existing IP Integrator design open,
# you can create a design using the following command:
#    create_bd_design $design_name

# Creating design if needed
set errMsg ""
set nRet 0

set cur_design [current_bd_design -quiet]
set list_cells [get_bd_cells -quiet]

if { ${design_name} eq "" } {
   # USE CASES:
   #    1) Design_name not set

   set errMsg "Please set the variable <design_name> to a non-empty value."
   set nRet 1

} elseif { ${cur_design} ne "" && ${list_cells} eq "" } {
   # USE CASES:
   #    2): Current design opened AND is empty AND names same.
   #    3): Current design opened AND is empty AND names diff; design_name NOT in project.
   #    4): Current design opened AND is empty AND names diff; design_name exists in project.

   if { $cur_design ne $design_name } {
      common::send_gid_msg -ssname BD::TCL -id 2001 -severity "INFO" "Changing value of <design_name> from <$design_name> to <$cur_design> since current design is empty."
      set design_name [get_property NAME $cur_design]
   }
   common::send_gid_msg -ssname BD::TCL -id 2002 -severity "INFO" "Constructing design in IPI design <$cur_design>..."

} elseif { ${cur_design} ne "" && $list_cells ne "" && $cur_design eq $design_name } {
   # USE CASES:
   #    5) Current design opened AND has components AND same names.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 1
} elseif { [get_files -quiet ${design_name}.bd] ne "" } {
   # USE CASES: 
   #    6) Current opened design, has components, but diff names, design_name exists in project.
   #    7) No opened design, design_name exists in project.

   set errMsg "Design <$design_name> already exists in your project, please set the variable <design_name> to another value."
   set nRet 2

} else {
   # USE CASES:
   #    8) No opened design, design_name not in project.
   #    9) Current opened design, has components, but diff names, design_name not in project.

   common::send_gid_msg -ssname BD::TCL -id 2003 -severity "INFO" "Currently there is no design <$design_name> in project, so creating one..."

   create_bd_design $design_name

   common::send_gid_msg -ssname BD::TCL -id 2004 -severity "INFO" "Making design <$design_name> as current_bd_design."
   current_bd_design $design_name

}

common::send_gid_msg -ssname BD::TCL -id 2005 -severity "INFO" "Currently the variable <design_name> is equal to \"$design_name\"."

if { $nRet != 0 } {
   catch {common::send_gid_msg -ssname BD::TCL -id 2006 -severity "ERROR" $errMsg}
   return $nRet
}

set bCheckIPsPassed 1
##################################################################
# CHECK IPs
##################################################################
set bCheckIPs 1
if { $bCheckIPs == 1 } {
   set list_check_ips "\ 
xilinx.com:ip:zynq_ultra_ps_e:3.5\
xilinx.com:ip:clk_wiz:6.0\
xilinx.com:ip:proc_sys_reset:5.0\
xilinx.com:ip:axi_crossbar:2.1\
xilinx.com:ip:axi_dwidth_converter:2.1\
xilinx.com:ip:dfx_axi_shutdown_manager:1.0\
xilinx.com:ip:xlslice:1.0\
xilinx.com:ip:xlconcat:2.1\
xilinx.com:ip:xlconstant:1.1\
"

   set list_ips_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2011 -severity "INFO" "Checking if the following IPs exist in the project's IP catalog: $list_check_ips ."

   foreach ip_vlnv $list_check_ips {
      set ip_obj [get_ipdefs -all $ip_vlnv]
      if { $ip_obj eq "" } {
         lappend list_ips_missing $ip_vlnv
      }
   }

   if { $list_ips_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2012 -severity "ERROR" "The following IPs are not found in the IP Catalog:\n  $list_ips_missing\n\nResolution: Please add the repository containing the IP(s) to the project." }
      set bCheckIPsPassed 0
   }

}

##################################################################
# CHECK Modules
##################################################################
set bCheckModules 1
if { $bCheckModules == 1 } {
   set list_check_mods "\ 
fzv10_ddr_guard_bd\
fzv4_axi_hp0_monitor\
ps8_axi_reset\
cnn_v10_half2x_clock_tree\
cnn_rtl_bd\
"

   set list_mods_missing ""
   common::send_gid_msg -ssname BD::TCL -id 2020 -severity "INFO" "Checking if the following modules exist in the project's sources: $list_check_mods ."

   foreach mod_vlnv $list_check_mods {
      if { [can_resolve_reference $mod_vlnv] == 0 } {
         lappend list_mods_missing $mod_vlnv
      }
   }

   if { $list_mods_missing ne "" } {
      catch {common::send_gid_msg -ssname BD::TCL -id 2021 -severity "ERROR" "The following module(s) are not found in the project: $list_mods_missing" }
      common::send_gid_msg -ssname BD::TCL -id 2022 -severity "INFO" "Please add source files for the missing module(s) above."
      set bCheckIPsPassed 0
   }
}

if { $bCheckIPsPassed != 1 } {
  common::send_gid_msg -ssname BD::TCL -id 2023 -severity "WARNING" "Will not continue with creation of design due to the error(s) above."
  return 3
}

##################################################################
# DESIGN PROCs
##################################################################



# Procedure to create entire design; Provide argument to make
# procedure reusable. If parentCell is "", will use root.
proc create_root_design { parentCell } {

  variable script_folder
  variable design_name

  if { $parentCell eq "" } {
     set parentCell [get_bd_cells /]
  }

  # Get object for parentCell
  set parentObj [get_bd_cells $parentCell]
  if { $parentObj == "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2090 -severity "ERROR" "Unable to find parent cell <$parentCell>!"}
     return
  }

  # Make sure parentObj is hier blk
  set parentType [get_property TYPE $parentObj]
  if { $parentType ne "hier" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2091 -severity "ERROR" "Parent <$parentObj> has TYPE = <$parentType>. Expected to be <hier>."}
     return
  }

  # Save current instance; Restore later
  set oldCurInst [current_bd_instance .]

  # Set parent object as current
  current_bd_instance $parentObj


  # Create interface ports

  # Create ports

  # Create instance: ps, and set properties
  set ps [ create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.5 ps ]
  set_property -dict [list \
    CONFIG.PSU_DDR_RAM_HIGHADDR {0xFFFFFFFF} \
    CONFIG.PSU_DDR_RAM_HIGHADDR_OFFSET {0x800000000} \
    CONFIG.PSU_DDR_RAM_LOWADDR_OFFSET {0x80000000} \
    CONFIG.PSU__ACT_DDR_FREQ_MHZ {799.992004} \
    CONFIG.PSU__CRF_APB__ACPU_CTRL__ACT_FREQMHZ {1199.988037} \
    CONFIG.PSU__CRF_APB__DBG_FPD_CTRL__ACT_FREQMHZ {249.997498} \
    CONFIG.PSU__CRF_APB__DBG_TSTMP_CTRL__ACT_FREQMHZ {249.997498} \
    CONFIG.PSU__CRF_APB__DDR_CTRL__ACT_FREQMHZ {399.996002} \
    CONFIG.PSU__CRF_APB__DPDMA_REF_CTRL__ACT_FREQMHZ {599.994019} \
    CONFIG.PSU__CRF_APB__GDMA_REF_CTRL__ACT_FREQMHZ {599.994019} \
    CONFIG.PSU__CRF_APB__GPU_REF_CTRL__ACT_FREQMHZ {599.994019} \
    CONFIG.PSU__CRF_APB__TOPSW_LSBUS_CTRL__ACT_FREQMHZ {99.999001} \
    CONFIG.PSU__CRF_APB__TOPSW_MAIN_CTRL__ACT_FREQMHZ {533.328003} \
    CONFIG.PSU__CRL_APB__ADMA_REF_CTRL__ACT_FREQMHZ {499.994995} \
    CONFIG.PSU__CRL_APB__AMS_REF_CTRL__ACT_FREQMHZ {49.999500} \
    CONFIG.PSU__CRL_APB__CPU_R5_CTRL__ACT_FREQMHZ {499.994995} \
    CONFIG.PSU__CRL_APB__DBG_LPD_CTRL__ACT_FREQMHZ {249.997498} \
    CONFIG.PSU__CRL_APB__DLL_REF_CTRL__ACT_FREQMHZ {999.989990} \
    CONFIG.PSU__CRL_APB__IOU_SWITCH_CTRL__ACT_FREQMHZ {266.664001} \
    CONFIG.PSU__CRL_APB__LPD_LSBUS_CTRL__ACT_FREQMHZ {99.999001} \
    CONFIG.PSU__CRL_APB__LPD_SWITCH_CTRL__ACT_FREQMHZ {499.994995} \
    CONFIG.PSU__CRL_APB__PCAP_CTRL__ACT_FREQMHZ {199.998001} \
    CONFIG.PSU__CRL_APB__PL0_REF_CTRL__ACT_FREQMHZ {99.999001} \
    CONFIG.PSU__CRL_APB__PL1_REF_CTRL__ACT_FREQMHZ {99.999001} \
    CONFIG.PSU__CRL_APB__PL1_REF_CTRL__FREQMHZ {100} \
    CONFIG.PSU__CRL_APB__PL1_REF_CTRL__SRCSEL {RPLL} \
    CONFIG.PSU__CRL_APB__TIMESTAMP_REF_CTRL__ACT_FREQMHZ {33.333000} \
    CONFIG.PSU__DDRC__DEVICE_CAPACITY {4096 MBits} \
    CONFIG.PSU__DDRC__ROW_ADDR_COUNT {15} \
    CONFIG.PSU__DDR_HIGH_ADDRESS_GUI_ENABLE {1} \
    CONFIG.PSU__FPGA_PL0_ENABLE {1} \
    CONFIG.PSU__FPGA_PL1_ENABLE {1} \
    CONFIG.PSU__FPGA_PL2_ENABLE {0} \
    CONFIG.PSU__FPGA_PL3_ENABLE {0} \
    CONFIG.PSU__MAXIGP0__DATA_WIDTH {32} \
    CONFIG.PSU__PL_CLK0_BUF {TRUE} \
    CONFIG.PSU__PL_CLK1_BUF {TRUE} \
    CONFIG.PSU__PROTECTION__MASTERS {USB1:NonSecure;0|USB0:NonSecure;0|S_AXI_LPD:NA;0|S_AXI_HPC1_FPD:NA;0|S_AXI_HPC0_FPD:NA;0|S_AXI_HP3_FPD:NA;0|S_AXI_HP2_FPD:NA;0|S_AXI_HP1_FPD:NA;0|S_AXI_HP0_FPD:NA;1|S_AXI_ACP:NA;0|S_AXI_ACE:NA;0|SD1:NonSecure;0|SD0:NonSecure;0|SATA1:NonSecure;0|SATA0:NonSecure;0|RPU1:Secure;1|RPU0:Secure;1|QSPI:NonSecure;0|PMU:NA;1|PCIe:NonSecure;0|NAND:NonSecure;0|LDMA:NonSecure;1|GPU:NonSecure;1|GEM3:NonSecure;0|GEM2:NonSecure;0|GEM1:NonSecure;0|GEM0:NonSecure;0|FDMA:NonSecure;1|DP:NonSecure;0|DAP:NA;1|Coresight:NA;1|CSU:NA;1|APU:NA;1}\
\
    CONFIG.PSU__PROTECTION__SLAVES {LPD;USB3_1_XHCI;FE300000;FE3FFFFF;0|LPD;USB3_1;FF9E0000;FF9EFFFF;0|LPD;USB3_0_XHCI;FE200000;FE2FFFFF;0|LPD;USB3_0;FF9D0000;FF9DFFFF;0|LPD;UART1;FF010000;FF01FFFF;0|LPD;UART0;FF000000;FF00FFFF;0|LPD;TTC3;FF140000;FF14FFFF;0|LPD;TTC2;FF130000;FF13FFFF;0|LPD;TTC1;FF120000;FF12FFFF;0|LPD;TTC0;FF110000;FF11FFFF;0|FPD;SWDT1;FD4D0000;FD4DFFFF;0|LPD;SWDT0;FF150000;FF15FFFF;0|LPD;SPI1;FF050000;FF05FFFF;0|LPD;SPI0;FF040000;FF04FFFF;0|FPD;SMMU_REG;FD5F0000;FD5FFFFF;1|FPD;SMMU;FD800000;FDFFFFFF;1|FPD;SIOU;FD3D0000;FD3DFFFF;1|FPD;SERDES;FD400000;FD47FFFF;1|LPD;SD1;FF170000;FF17FFFF;0|LPD;SD0;FF160000;FF16FFFF;0|FPD;SATA;FD0C0000;FD0CFFFF;0|LPD;RTC;FFA60000;FFA6FFFF;1|LPD;RSA_CORE;FFCE0000;FFCEFFFF;1|LPD;RPU;FF9A0000;FF9AFFFF;1|LPD;R5_TCM_RAM_GLOBAL;FFE00000;FFE3FFFF;1|LPD;R5_1_Instruction_Cache;FFEC0000;FFECFFFF;1|LPD;R5_1_Data_Cache;FFED0000;FFEDFFFF;1|LPD;R5_1_BTCM_GLOBAL;FFEB0000;FFEBFFFF;1|LPD;R5_1_ATCM_GLOBAL;FFE90000;FFE9FFFF;1|LPD;R5_0_Instruction_Cache;FFE40000;FFE4FFFF;1|LPD;R5_0_Data_Cache;FFE50000;FFE5FFFF;1|LPD;R5_0_BTCM_GLOBAL;FFE20000;FFE2FFFF;1|LPD;R5_0_ATCM_GLOBAL;FFE00000;FFE0FFFF;1|LPD;QSPI_Linear_Address;C0000000;DFFFFFFF;1|LPD;QSPI;FF0F0000;FF0FFFFF;0|LPD;PMU_RAM;FFDC0000;FFDDFFFF;1|LPD;PMU_GLOBAL;FFD80000;FFDBFFFF;1|FPD;PCIE_MAIN;FD0E0000;FD0EFFFF;0|FPD;PCIE_LOW;E0000000;EFFFFFFF;0|FPD;PCIE_HIGH2;8000000000;BFFFFFFFFF;0|FPD;PCIE_HIGH1;600000000;7FFFFFFFF;0|FPD;PCIE_DMA;FD0F0000;FD0FFFFF;0|FPD;PCIE_ATTRIB;FD480000;FD48FFFF;0|LPD;OCM_XMPU_CFG;FFA70000;FFA7FFFF;1|LPD;OCM_SLCR;FF960000;FF96FFFF;1|OCM;OCM;FFFC0000;FFFFFFFF;1|LPD;NAND;FF100000;FF10FFFF;0|LPD;MBISTJTAG;FFCF0000;FFCFFFFF;1|LPD;LPD_XPPU_SINK;FF9C0000;FF9CFFFF;1|LPD;LPD_XPPU;FF980000;FF98FFFF;1|LPD;LPD_SLCR_SECURE;FF4B0000;FF4DFFFF;1|LPD;LPD_SLCR;FF410000;FF4AFFFF;1|LPD;LPD_GPV;FE100000;FE1FFFFF;1|LPD;LPD_DMA_7;FFAF0000;FFAFFFFF;1|LPD;LPD_DMA_6;FFAE0000;FFAEFFFF;1|LPD;LPD_DMA_5;FFAD0000;FFADFFFF;1|LPD;LPD_DMA_4;FFAC0000;FFACFFFF;1|LPD;LPD_DMA_3;FFAB0000;FFABFFFF;1|LPD;LPD_DMA_2;FFAA0000;FFAAFFFF;1|LPD;LPD_DMA_1;FFA90000;FFA9FFFF;1|LPD;LPD_DMA_0;FFA80000;FFA8FFFF;1|LPD;IPI_CTRL;FF380000;FF3FFFFF;1|LPD;IOU_SLCR;FF180000;FF23FFFF;1|LPD;IOU_SECURE_SLCR;FF240000;FF24FFFF;1|LPD;IOU_SCNTRS;FF260000;FF26FFFF;1|LPD;IOU_SCNTR;FF250000;FF25FFFF;1|LPD;IOU_GPV;FE000000;FE0FFFFF;1|LPD;I2C1;FF030000;FF03FFFF;0|LPD;I2C0;FF020000;FF02FFFF;0|FPD;GPU;FD4B0000;FD4BFFFF;1|LPD;GPIO;FF0A0000;FF0AFFFF;1|LPD;GEM3;FF0E0000;FF0EFFFF;0|LPD;GEM2;FF0D0000;FF0DFFFF;0|LPD;GEM1;FF0C0000;FF0CFFFF;0|LPD;GEM0;FF0B0000;FF0BFFFF;0|FPD;FPD_XMPU_SINK;FD4F0000;FD4FFFFF;1|FPD;FPD_XMPU_CFG;FD5D0000;FD5DFFFF;1|FPD;FPD_SLCR_SECURE;FD690000;FD6CFFFF;1|FPD;FPD_SLCR;FD610000;FD68FFFF;1|FPD;FPD_DMA_CH7;FD570000;FD57FFFF;1|FPD;FPD_DMA_CH6;FD560000;FD56FFFF;1|FPD;FPD_DMA_CH5;FD550000;FD55FFFF;1|FPD;FPD_DMA_CH4;FD540000;FD54FFFF;1|FPD;FPD_DMA_CH3;FD530000;FD53FFFF;1|FPD;FPD_DMA_CH2;FD520000;FD52FFFF;1|FPD;FPD_DMA_CH1;FD510000;FD51FFFF;1|FPD;FPD_DMA_CH0;FD500000;FD50FFFF;1|LPD;EFUSE;FFCC0000;FFCCFFFF;1|FPD;Display\
Port;FD4A0000;FD4AFFFF;0|FPD;DPDMA;FD4C0000;FD4CFFFF;0|FPD;DDR_XMPU5_CFG;FD050000;FD05FFFF;1|FPD;DDR_XMPU4_CFG;FD040000;FD04FFFF;1|FPD;DDR_XMPU3_CFG;FD030000;FD03FFFF;1|FPD;DDR_XMPU2_CFG;FD020000;FD02FFFF;1|FPD;DDR_XMPU1_CFG;FD010000;FD01FFFF;1|FPD;DDR_XMPU0_CFG;FD000000;FD00FFFF;1|FPD;DDR_QOS_CTRL;FD090000;FD09FFFF;1|FPD;DDR_PHY;FD080000;FD08FFFF;1|DDR;DDR_LOW;0;7FFFFFFF;1|DDR;DDR_HIGH;800000000;87FFFFFFF;1|FPD;DDDR_CTRL;FD070000;FD070FFF;1|LPD;Coresight;FE800000;FEFFFFFF;1|LPD;CSU_DMA;FFC80000;FFC9FFFF;1|LPD;CSU;FFCA0000;FFCAFFFF;1|LPD;CRL_APB;FF5E0000;FF85FFFF;1|FPD;CRF_APB;FD1A0000;FD2DFFFF;1|FPD;CCI_REG;FD5E0000;FD5EFFFF;1|LPD;CAN1;FF070000;FF07FFFF;0|LPD;CAN0;FF060000;FF06FFFF;0|FPD;APU;FD5C0000;FD5CFFFF;1|LPD;APM_INTC_IOU;FFA20000;FFA2FFFF;1|LPD;APM_FPD_LPD;FFA30000;FFA3FFFF;1|FPD;APM_5;FD490000;FD49FFFF;1|FPD;APM_0;FD0B0000;FD0BFFFF;1|LPD;APM2;FFA10000;FFA1FFFF;1|LPD;APM1;FFA00000;FFA0FFFF;1|LPD;AMS;FFA50000;FFA5FFFF;1|FPD;AFI_5;FD3B0000;FD3BFFFF;1|FPD;AFI_4;FD3A0000;FD3AFFFF;1|FPD;AFI_3;FD390000;FD39FFFF;1|FPD;AFI_2;FD380000;FD38FFFF;1|FPD;AFI_1;FD370000;FD37FFFF;1|FPD;AFI_0;FD360000;FD36FFFF;1|LPD;AFIFM6;FF9B0000;FF9BFFFF;1|FPD;ACPU_GIC;F9010000;F907FFFF;1}\
\
    CONFIG.PSU__SAXIGP2__DATA_WIDTH {64} \
    CONFIG.PSU__USE__IRQ0 {0} \
    CONFIG.PSU__USE__IRQ1 {0} \
    CONFIG.PSU__USE__M_AXI_GP0 {1} \
    CONFIG.PSU__USE__M_AXI_GP1 {0} \
    CONFIG.PSU__USE__M_AXI_GP2 {0} \
    CONFIG.PSU__USE__S_AXI_GP0 {0} \
    CONFIG.PSU__USE__S_AXI_GP1 {0} \
    CONFIG.PSU__USE__S_AXI_GP2 {1} \
    CONFIG.PSU__USE__S_AXI_GP3 {0} \
    CONFIG.PSU__USE__S_AXI_GP4 {0} \
    CONFIG.PSU__USE__S_AXI_GP5 {0} \
    CONFIG.PSU__USE__S_AXI_GP6 {0} \
  ] $ps


  # Create instance: core, and set properties
  set core [create_bd_cell -type module -reference cnn_rtl_bd core]

  # Create instance: guard, and set properties
  set block_name fzv10_ddr_guard_bd
  set block_cell_name guard
  if { [catch {set guard [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $guard eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
    set_property -dict [list \
    CONFIG.ABI_VERSION_VALUE {0x000A0005} \
    CONFIG.CAPS_VALUE {0x00000FFF} \
    CONFIG.ID_VALUE {0x465A5641} \
  ] $guard


  # Create instance: hp0_monitor, and set properties
  set block_name fzv4_axi_hp0_monitor
  set block_cell_name hp0_monitor
  if { [catch {set hp0_monitor [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $hp0_monitor eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
  
  # Create instance: reset, and set properties
  set block_name ps8_axi_reset
  set block_cell_name reset
  if { [catch {set reset [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $reset eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
  
  # Create instance: clock_wiz, and set properties
  set clock_wiz [ create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clock_wiz ]
  set_property -dict [list \
    CONFIG.CLKOUT1_DRIVES {No_buffer} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {400.0} \
    CONFIG.NUM_OUT_CLKS {1} \
    CONFIG.PRIM_IN_FREQ {99.999001} \
    CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.USE_LOCKED {true} \
    CONFIG.USE_RESET {false} \
  ] $clock_wiz


  # Create instance: half2x_clock_tree, and set properties
  set block_name cnn_v10_half2x_clock_tree
  set block_cell_name half2x_clock_tree
  if { [catch {set half2x_clock_tree [create_bd_cell -type module -reference $block_name $block_cell_name] } errmsg] } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2095 -severity "ERROR" "Unable to add referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   } elseif { $half2x_clock_tree eq "" } {
     catch {common::send_gid_msg -ssname BD::TCL -id 2096 -severity "ERROR" "Unable to referenced block <$block_name>. Please add the files for ${block_name}'s definition into the project."}
     return 1
   }
  
  # Create instance: platform_reset, and set properties
  set platform_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 platform_reset ]
  set_property CONFIG.C_AUX_RESET_HIGH {0} $platform_reset


  # Create instance: core_reset, and set properties
  set core_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 core_reset ]
  set_property CONFIG.C_AUX_RESET_HIGH {0} $core_reset


  # Create instance: fast_core_reset, and set properties
  set fast_core_reset [ create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 fast_core_reset ]
  set_property CONFIG.C_AUX_RESET_HIGH {0} $fast_core_reset


  # Create instance: ctrl_xbar, and set properties
  set ctrl_xbar [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 ctrl_xbar ]
  set_property -dict [list \
    CONFIG.NUM_MI {2} \
    CONFIG.NUM_SI {1} \
    CONFIG.XBAR_DATA_WIDTH {32} \
  ] $ctrl_xbar


  # Create instance: data_xbar, and set properties
  set data_xbar [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_crossbar:2.1 data_xbar ]
  set_property -dict [list \
    CONFIG.ADDR_RANGES {2} \
    CONFIG.ADDR_WIDTH {64} \
    CONFIG.CONNECTIVITY_MODE {SAMD} \
    CONFIG.DATA_WIDTH {128} \
    CONFIG.ID_WIDTH {4} \
    CONFIG.M00_A00_ADDR_WIDTH {30} \
    CONFIG.M00_A00_BASE_ADDR {0x0000000040000000} \
    CONFIG.M00_A01_ADDR_WIDTH {30} \
    CONFIG.M00_A01_BASE_ADDR {0x0000000800000000} \
    CONFIG.M00_READ_ISSUING {16} \
    CONFIG.M00_S00_READ_CONNECTIVITY {1} \
    CONFIG.M00_S00_WRITE_CONNECTIVITY {0} \
    CONFIG.M00_S01_READ_CONNECTIVITY {1} \
    CONFIG.M00_S01_WRITE_CONNECTIVITY {0} \
    CONFIG.M00_S02_READ_CONNECTIVITY {1} \
    CONFIG.M00_S02_WRITE_CONNECTIVITY {0} \
    CONFIG.M00_S03_READ_CONNECTIVITY {0} \
    CONFIG.M00_S03_WRITE_CONNECTIVITY {1} \
    CONFIG.M00_S04_READ_CONNECTIVITY {1} \
    CONFIG.M00_S04_WRITE_CONNECTIVITY {0} \
    CONFIG.M00_S05_READ_CONNECTIVITY {0} \
    CONFIG.M00_S05_WRITE_CONNECTIVITY {1} \
    CONFIG.M00_WRITE_ISSUING {16} \
    CONFIG.NUM_MI {1} \
    CONFIG.NUM_SI {6} \
    CONFIG.PROTOCOL {AXI4} \
  ] $data_xbar


  # Create instance: data_dwidth, and set properties
  set data_dwidth [ create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dwidth_converter:2.1 data_dwidth ]
  set_property -dict [list \
    CONFIG.ADDR_WIDTH {64} \
    CONFIG.MI_DATA_WIDTH {64} \
    CONFIG.PACKING_LEVEL {1} \
    CONFIG.PROTOCOL {AXI4} \
    CONFIG.READ_WRITE_MODE {READ_WRITE} \
    CONFIG.SI_DATA_WIDTH {128} \
    CONFIG.SI_ID_WIDTH {4} \
  ] $data_dwidth


  # Create instance: shutdown_0, and set properties
  set shutdown_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_0 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_0


  # Create instance: shutdown_1, and set properties
  set shutdown_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_1 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_1


  # Create instance: shutdown_2, and set properties
  set shutdown_2 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_2 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_2


  # Create instance: shutdown_3, and set properties
  set shutdown_3 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_3 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_3


  # Create instance: shutdown_4, and set properties
  set shutdown_4 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_4 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_4


  # Create instance: shutdown_5, and set properties
  set shutdown_5 [ create_bd_cell -type ip -vlnv xilinx.com:ip:dfx_axi_shutdown_manager:1.0 shutdown_5 ]
  set_property -dict [list \
    CONFIG.CTRL_INTERFACE_TYPE {0} \
    CONFIG.DP_AXI_ADDR_WIDTH {64} \
    CONFIG.DP_AXI_ARUSER_WIDTH {1} \
    CONFIG.DP_AXI_AWUSER_WIDTH {1} \
    CONFIG.DP_AXI_BUSER_WIDTH {1} \
    CONFIG.DP_AXI_DATA_WIDTH {128} \
    CONFIG.DP_AXI_ID_WIDTH {1} \
    CONFIG.DP_AXI_RUSER_WIDTH {1} \
    CONFIG.DP_AXI_WUSER_WIDTH {1} \
    CONFIG.DP_PROTOCOL {AXI4MM} \
    CONFIG.RESET_ACTIVE_LEVEL {0} \
    CONFIG.RP_IS_MASTER {true} \
  ] $shutdown_5


  # Create instance: req_slice_0, and set properties
  set req_slice_0 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_0 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {0} \
    CONFIG.DIN_TO {0} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_0


  # Create instance: req_slice_1, and set properties
  set req_slice_1 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_1 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {1} \
    CONFIG.DIN_TO {1} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_1


  # Create instance: req_slice_2, and set properties
  set req_slice_2 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_2 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {2} \
    CONFIG.DIN_TO {2} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_2


  # Create instance: req_slice_3, and set properties
  set req_slice_3 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_3 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {3} \
    CONFIG.DIN_TO {3} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_3


  # Create instance: req_slice_4, and set properties
  set req_slice_4 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_4 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {4} \
    CONFIG.DIN_TO {4} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_4


  # Create instance: req_slice_5, and set properties
  set req_slice_5 [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlslice:1.0 req_slice_5 ]
  set_property -dict [list \
    CONFIG.DIN_FROM {5} \
    CONFIG.DIN_TO {5} \
    CONFIG.DIN_WIDTH {6} \
    CONFIG.DOUT_WIDTH {1} \
  ] $req_slice_5


  # Create instance: ack_all, and set properties
  set ack_all [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_all ]
  set_property CONFIG.NUM_PORTS {6} $ack_all


  # Create instance: ack_rd, and set properties
  set ack_rd [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_rd ]
  set_property CONFIG.NUM_PORTS {6} $ack_rd


  # Create instance: ack_wr, and set properties
  set ack_wr [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 ack_wr ]
  set_property CONFIG.NUM_PORTS {6} $ack_wr


  # Create instance: const_zero, and set properties
  set const_zero [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_zero ]
  set_property -dict [list \
    CONFIG.CONST_VAL {0} \
    CONFIG.CONST_WIDTH {1} \
  ] $const_zero


  # Create instance: const_one, and set properties
  set const_one [ create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_one ]
  set_property -dict [list \
    CONFIG.CONST_VAL {1} \
    CONFIG.CONST_WIDTH {1} \
  ] $const_one


  # Create interface connections
  connect_bd_intf_net -intf_net ctrl_xbar_M00_AXI [get_bd_intf_pins ctrl_xbar/M00_AXI] [get_bd_intf_pins core/s_axi_control]
  connect_bd_intf_net -intf_net ctrl_xbar_M01_AXI [get_bd_intf_pins ctrl_xbar/M01_AXI] [get_bd_intf_pins guard/S_AXI]
  connect_bd_intf_net -intf_net data_dwidth_M_AXI [get_bd_intf_pins data_dwidth/M_AXI] [get_bd_intf_pins ps/S_AXI_HP0_FPD]
connect_bd_intf_net -intf_net [get_bd_intf_nets data_dwidth_M_AXI] [get_bd_intf_pins data_dwidth/M_AXI] [get_bd_intf_pins hp0_monitor/MON_AXI]
  connect_bd_intf_net -intf_net data_xbar_M00_AXI [get_bd_intf_pins data_xbar/M00_AXI] [get_bd_intf_pins data_dwidth/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_act_a_r [get_bd_intf_pins core/m_axi_g_act_a_r] [get_bd_intf_pins shutdown_2/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_act_a_w [get_bd_intf_pins core/m_axi_g_act_a_w] [get_bd_intf_pins shutdown_3/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_act_b_r [get_bd_intf_pins core/m_axi_g_act_b_r] [get_bd_intf_pins shutdown_4/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_act_b_w [get_bd_intf_pins core/m_axi_g_act_b_w] [get_bd_intf_pins shutdown_5/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_param1 [get_bd_intf_pins core/m_axi_g_param1] [get_bd_intf_pins shutdown_0/S_AXI]
  connect_bd_intf_net -intf_net core_m_axi_g_param2 [get_bd_intf_pins core/m_axi_g_param2] [get_bd_intf_pins shutdown_1/S_AXI]
  connect_bd_intf_net -intf_net ps_M_AXI_HPM0_FPD [get_bd_intf_pins ps/M_AXI_HPM0_FPD] [get_bd_intf_pins ctrl_xbar/S00_AXI]
  connect_bd_intf_net -intf_net shutdown_0_M_AXI [get_bd_intf_pins shutdown_0/M_AXI] [get_bd_intf_pins data_xbar/S00_AXI]
  connect_bd_intf_net -intf_net shutdown_1_M_AXI [get_bd_intf_pins shutdown_1/M_AXI] [get_bd_intf_pins data_xbar/S01_AXI]
  connect_bd_intf_net -intf_net shutdown_2_M_AXI [get_bd_intf_pins shutdown_2/M_AXI] [get_bd_intf_pins data_xbar/S02_AXI]
  connect_bd_intf_net -intf_net shutdown_3_M_AXI [get_bd_intf_pins shutdown_3/M_AXI] [get_bd_intf_pins data_xbar/S03_AXI]
  connect_bd_intf_net -intf_net shutdown_4_M_AXI [get_bd_intf_pins shutdown_4/M_AXI] [get_bd_intf_pins data_xbar/S04_AXI]
  connect_bd_intf_net -intf_net shutdown_5_M_AXI [get_bd_intf_pins shutdown_5/M_AXI] [get_bd_intf_pins data_xbar/S05_AXI]

  # Create port connections
  connect_bd_net -net ack_all_dout  [get_bd_pins ack_all/dout] \
  [get_bd_pins guard/shutdown_ack]
  connect_bd_net -net ack_rd_dout  [get_bd_pins ack_rd/dout] \
  [get_bd_pins guard/shutdown_rd_ack]
  connect_bd_net -net ack_wr_dout  [get_bd_pins ack_wr/dout] \
  [get_bd_pins guard/shutdown_wr_ack]
  connect_bd_net -net clock_wiz_clk_out1  [get_bd_pins clock_wiz/clk_out1] \
  [get_bd_pins half2x_clock_tree/root_clk_400]
  connect_bd_net -net clock_wiz_locked  [get_bd_pins clock_wiz/locked] \
  [get_bd_pins platform_reset/dcm_locked] \
  [get_bd_pins core_reset/dcm_locked] \
  [get_bd_pins fast_core_reset/dcm_locked]
  connect_bd_net -net const_one_dout  [get_bd_pins const_one/dout] \
  [get_bd_pins platform_reset/aux_reset_in]
  connect_bd_net -net const_zero_dout  [get_bd_pins const_zero/dout] \
  [get_bd_pins platform_reset/mb_debug_sys_rst] \
  [get_bd_pins core_reset/mb_debug_sys_rst] \
  [get_bd_pins fast_core_reset/mb_debug_sys_rst]
  connect_bd_net -net core_reset_peripheral_aresetn  [get_bd_pins core_reset/peripheral_aresetn] \
  [get_bd_pins core/ap_rst_n] \
  [get_bd_pins guard/core_reset_feedback_aresetn]
  connect_bd_net -net fast_core_reset_peripheral_aresetn  [get_bd_pins fast_core_reset/peripheral_aresetn] \
  [get_bd_pins core_reset/aux_reset_in]
  connect_bd_net -net fast_core_reset_peripheral_reset  [get_bd_pins fast_core_reset/peripheral_reset] \
  [get_bd_pins core/pw_fast_rst]
  connect_bd_net -net guard_core_reset_req  [get_bd_pins guard/core_reset_req] \
  [get_bd_pins core_reset/ext_reset_in] \
  [get_bd_pins fast_core_reset/ext_reset_in]
  connect_bd_net -net guard_hls_ap_start  [get_bd_pins guard/hls_ap_start] \
  [get_bd_pins core/ap_start]
  connect_bd_net -net guard_shutdown_request  [get_bd_pins guard/shutdown_request] \
  [get_bd_pins req_slice_0/Din] \
  [get_bd_pins req_slice_1/Din] \
  [get_bd_pins req_slice_2/Din] \
  [get_bd_pins req_slice_3/Din] \
  [get_bd_pins req_slice_4/Din] \
  [get_bd_pins req_slice_5/Din]
  connect_bd_net -net half2x_clock_tree_driver_job_clk_200  [get_bd_pins half2x_clock_tree/driver_job_clk_200] \
  [get_bd_pins ps/maxihpm0_fpd_aclk] \
  [get_bd_pins ps/saxihp0_fpd_aclk] \
  [get_bd_pins ctrl_xbar/ACLK] \
  [get_bd_pins ctrl_xbar/S00_ACLK] \
  [get_bd_pins ctrl_xbar/M00_ACLK] \
  [get_bd_pins ctrl_xbar/M01_ACLK] \
  [get_bd_pins data_xbar/aclk] \
  [get_bd_pins data_dwidth/s_axi_aclk] \
  [get_bd_pins core/ap_clk] \
  [get_bd_pins guard/clk] \
  [get_bd_pins reset/clk] \
  [get_bd_pins hp0_monitor/clk] \
  [get_bd_pins platform_reset/slowest_sync_clk] \
  [get_bd_pins core_reset/slowest_sync_clk] \
  [get_bd_pins shutdown_0/clk] \
  [get_bd_pins shutdown_1/clk] \
  [get_bd_pins shutdown_2/clk] \
  [get_bd_pins shutdown_3/clk] \
  [get_bd_pins shutdown_4/clk] \
  [get_bd_pins shutdown_5/clk]
  connect_bd_net -net half2x_clock_tree_pw_local_clk_400  [get_bd_pins half2x_clock_tree/pw_local_clk_400] \
  [get_bd_pins core/pw_fast_clk] \
  [get_bd_pins fast_core_reset/slowest_sync_clk]
  connect_bd_net -net core_ap_done  [get_bd_pins core/ap_done] \
  [get_bd_pins guard/hls_ap_done]
  connect_bd_net -net core_ap_idle  [get_bd_pins core/ap_idle] \
  [get_bd_pins guard/hls_ap_idle]
  connect_bd_net -net core_ap_ready  [get_bd_pins core/ap_ready] \
  [get_bd_pins guard/hls_ap_ready]
  connect_bd_net -net core_protocol_error  [get_bd_pins core/protocol_error] \
  [get_bd_pins guard/hls_protocol_error]
  connect_bd_net -net core_protocol_error_ap_vld  [get_bd_pins core/protocol_error_ap_vld] \
  [get_bd_pins guard/hls_protocol_error_ap_vld]
  connect_bd_net -net hp0_monitor_down_ar_fire  [get_bd_pins hp0_monitor/down_ar_fire] \
  [get_bd_pins guard/down_ar_fire]
  connect_bd_net -net hp0_monitor_down_aw_fire  [get_bd_pins hp0_monitor/down_aw_fire] \
  [get_bd_pins guard/down_aw_fire]
  connect_bd_net -net hp0_monitor_down_b_fire  [get_bd_pins hp0_monitor/down_b_fire] \
  [get_bd_pins guard/down_b_fire]
  connect_bd_net -net hp0_monitor_down_bresp  [get_bd_pins hp0_monitor/down_bresp] \
  [get_bd_pins guard/down_bresp]
  connect_bd_net -net hp0_monitor_down_r_fire  [get_bd_pins hp0_monitor/down_r_fire] \
  [get_bd_pins guard/down_r_fire]
  connect_bd_net -net hp0_monitor_down_rlast_fire  [get_bd_pins hp0_monitor/down_rlast_fire] \
  [get_bd_pins guard/down_rlast_fire]
  connect_bd_net -net hp0_monitor_down_rresp  [get_bd_pins hp0_monitor/down_rresp] \
  [get_bd_pins guard/down_rresp]
  connect_bd_net -net hp0_monitor_down_wlast_fire  [get_bd_pins hp0_monitor/down_wlast_fire] \
  [get_bd_pins guard/down_wlast_fire]
  connect_bd_net -net platform_reset_peripheral_aresetn  [get_bd_pins platform_reset/peripheral_aresetn] \
  [get_bd_pins ctrl_xbar/ARESETN] \
  [get_bd_pins ctrl_xbar/S00_ARESETN] \
  [get_bd_pins ctrl_xbar/M00_ARESETN] \
  [get_bd_pins ctrl_xbar/M01_ARESETN] \
  [get_bd_pins data_xbar/aresetn] \
  [get_bd_pins data_dwidth/s_axi_aresetn] \
  [get_bd_pins hp0_monitor/resetn] \
  [get_bd_pins shutdown_0/resetn] \
  [get_bd_pins shutdown_1/resetn] \
  [get_bd_pins shutdown_2/resetn] \
  [get_bd_pins shutdown_3/resetn] \
  [get_bd_pins shutdown_4/resetn] \
  [get_bd_pins shutdown_5/resetn] \
  [get_bd_pins fast_core_reset/aux_reset_in]
  connect_bd_net -net platform_reset_peripheral_reset  [get_bd_pins platform_reset/peripheral_reset] \
  [get_bd_pins guard/rst]
  connect_bd_net -net ps_pl_clk1  [get_bd_pins ps/pl_clk1] \
  [get_bd_pins clock_wiz/clk_in1]
  connect_bd_net -net ps_pl_resetn0  [get_bd_pins ps/pl_resetn0] \
  [get_bd_pins reset/ps_resetn]
  connect_bd_net -net req_slice_0_Dout  [get_bd_pins req_slice_0/Dout] \
  [get_bd_pins shutdown_0/request_shutdown]
  connect_bd_net -net req_slice_1_Dout  [get_bd_pins req_slice_1/Dout] \
  [get_bd_pins shutdown_1/request_shutdown]
  connect_bd_net -net req_slice_2_Dout  [get_bd_pins req_slice_2/Dout] \
  [get_bd_pins shutdown_2/request_shutdown]
  connect_bd_net -net req_slice_3_Dout  [get_bd_pins req_slice_3/Dout] \
  [get_bd_pins shutdown_3/request_shutdown]
  connect_bd_net -net req_slice_4_Dout  [get_bd_pins req_slice_4/Dout] \
  [get_bd_pins shutdown_4/request_shutdown]
  connect_bd_net -net req_slice_5_Dout  [get_bd_pins req_slice_5/Dout] \
  [get_bd_pins shutdown_5/request_shutdown]
  connect_bd_net -net reset_rst  [get_bd_pins reset/rst] \
  [get_bd_pins platform_reset/ext_reset_in]
  connect_bd_net -net shutdown_0_in_shutdown  [get_bd_pins shutdown_0/in_shutdown] \
  [get_bd_pins ack_all/In0]
  connect_bd_net -net shutdown_0_rd_in_shutdown  [get_bd_pins shutdown_0/rd_in_shutdown] \
  [get_bd_pins ack_rd/In0]
  connect_bd_net -net shutdown_0_wr_in_shutdown  [get_bd_pins shutdown_0/wr_in_shutdown] \
  [get_bd_pins ack_wr/In0]
  connect_bd_net -net shutdown_1_in_shutdown  [get_bd_pins shutdown_1/in_shutdown] \
  [get_bd_pins ack_all/In1]
  connect_bd_net -net shutdown_1_rd_in_shutdown  [get_bd_pins shutdown_1/rd_in_shutdown] \
  [get_bd_pins ack_rd/In1]
  connect_bd_net -net shutdown_1_wr_in_shutdown  [get_bd_pins shutdown_1/wr_in_shutdown] \
  [get_bd_pins ack_wr/In1]
  connect_bd_net -net shutdown_2_in_shutdown  [get_bd_pins shutdown_2/in_shutdown] \
  [get_bd_pins ack_all/In2]
  connect_bd_net -net shutdown_2_rd_in_shutdown  [get_bd_pins shutdown_2/rd_in_shutdown] \
  [get_bd_pins ack_rd/In2]
  connect_bd_net -net shutdown_2_wr_in_shutdown  [get_bd_pins shutdown_2/wr_in_shutdown] \
  [get_bd_pins ack_wr/In2]
  connect_bd_net -net shutdown_3_in_shutdown  [get_bd_pins shutdown_3/in_shutdown] \
  [get_bd_pins ack_all/In3]
  connect_bd_net -net shutdown_3_rd_in_shutdown  [get_bd_pins shutdown_3/rd_in_shutdown] \
  [get_bd_pins ack_rd/In3]
  connect_bd_net -net shutdown_3_wr_in_shutdown  [get_bd_pins shutdown_3/wr_in_shutdown] \
  [get_bd_pins ack_wr/In3]
  connect_bd_net -net shutdown_4_in_shutdown  [get_bd_pins shutdown_4/in_shutdown] \
  [get_bd_pins ack_all/In4]
  connect_bd_net -net shutdown_4_rd_in_shutdown  [get_bd_pins shutdown_4/rd_in_shutdown] \
  [get_bd_pins ack_rd/In4]
  connect_bd_net -net shutdown_4_wr_in_shutdown  [get_bd_pins shutdown_4/wr_in_shutdown] \
  [get_bd_pins ack_wr/In4]
  connect_bd_net -net shutdown_5_in_shutdown  [get_bd_pins shutdown_5/in_shutdown] \
  [get_bd_pins ack_all/In5]
  connect_bd_net -net shutdown_5_rd_in_shutdown  [get_bd_pins shutdown_5/rd_in_shutdown] \
  [get_bd_pins ack_rd/In5]
  connect_bd_net -net shutdown_5_wr_in_shutdown  [get_bd_pins shutdown_5/wr_in_shutdown] \
  [get_bd_pins ack_wr/In5]

  # Create address segments
  assign_bd_address -offset 0xA4010000 -range 0x00010000 -with_name GUARD_A401_64K -target_address_space [get_bd_addr_spaces ps/Data] [get_bd_addr_segs guard/S_AXI/reg0] -force
  assign_bd_address -offset 0xA4000000 -range 0x00010000 -with_name CORE_A400_64K -target_address_space [get_bd_addr_spaces ps/Data] [get_bd_addr_segs core/s_axi_control/reg0] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_2 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_a_r] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_2 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_a_r] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_3 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_a_w] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_3 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_a_w] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_4 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_b_r] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_4 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_b_r] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_5 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_b_w] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_5 -target_address_space [get_bd_addr_spaces core/m_axi_g_act_b_w] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_0 -target_address_space [get_bd_addr_spaces core/m_axi_g_param1] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_0 -target_address_space [get_bd_addr_spaces core/m_axi_g_param1] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force
  assign_bd_address -offset 0x000800000000 -range 0x40000000 -with_name DDR_HIGH_1 -target_address_space [get_bd_addr_spaces core/m_axi_g_param2] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_HIGH] -force
  assign_bd_address -offset 0x40000000 -range 0x40000000 -with_name DDR_LOW_1 -target_address_space [get_bd_addr_spaces core/m_axi_g_param2] [get_bd_addr_segs ps/SAXIGP2/HP0_DDR_LOW] -force


  # Restore current instance
  current_bd_instance $oldCurInst

  validate_bd_design
  save_bd_design
}
# End of create_root_design()


##################################################################
# MAIN FLOW
##################################################################

create_root_design ""


