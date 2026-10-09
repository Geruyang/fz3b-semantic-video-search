# Definitional proc to organize widgets for parameters.
proc init_gui { IPINST } {
  ipgui::add_param $IPINST -name "Component_Name"
  #Adding Page
  set Page_0 [ipgui::add_page $IPINST -name "Page 0"]
  #Adding Group
  set group_0 [ipgui::add_group $IPINST -name "group 0" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_param1}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_ENABLE_ID_PORTS" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_ID_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_DATA_WIDTH" -parent ${group_0} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_ENABLE_USER_PORTS" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_AWUSER_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_WUSER_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_BUSER_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_ARUSER_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_RUSER_WIDTH" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_USER_VALUE" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_PROT_VALUE" -parent ${group_0}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM1_CACHE_VALUE" -parent ${group_0}

  #Adding Group
  set group_1 [ipgui::add_group $IPINST -name "group 1" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_param2}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_ENABLE_ID_PORTS" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_ID_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_DATA_WIDTH" -parent ${group_1} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_ENABLE_USER_PORTS" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_AWUSER_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_WUSER_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_BUSER_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_ARUSER_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_RUSER_WIDTH" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_USER_VALUE" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_PROT_VALUE" -parent ${group_1}
  ipgui::add_param $IPINST -name "C_M_AXI_G_PARAM2_CACHE_VALUE" -parent ${group_1}

  #Adding Group
  set group_2 [ipgui::add_group $IPINST -name "group 2" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_act_a_r}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_ID_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_DATA_WIDTH" -parent ${group_2} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_AWUSER_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_WUSER_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_BUSER_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_ARUSER_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_RUSER_WIDTH" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_USER_VALUE" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_PROT_VALUE" -parent ${group_2}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_R_CACHE_VALUE" -parent ${group_2}

  #Adding Group
  set group_3 [ipgui::add_group $IPINST -name "group 3" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_act_a_w}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_ID_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_DATA_WIDTH" -parent ${group_3} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_AWUSER_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_WUSER_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_BUSER_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_ARUSER_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_RUSER_WIDTH" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_USER_VALUE" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_PROT_VALUE" -parent ${group_3}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_A_W_CACHE_VALUE" -parent ${group_3}

  #Adding Group
  set group_4 [ipgui::add_group $IPINST -name "group 4" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_act_b_r}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_ID_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_DATA_WIDTH" -parent ${group_4} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_AWUSER_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_WUSER_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_BUSER_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_ARUSER_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_RUSER_WIDTH" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_USER_VALUE" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_PROT_VALUE" -parent ${group_4}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_R_CACHE_VALUE" -parent ${group_4}

  #Adding Group
  set group_5 [ipgui::add_group $IPINST -name "group 5" -parent ${Page_0} -display_name {AXI4 Master Interface m_axi_g_act_b_w}]
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_ID_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_DATA_WIDTH" -parent ${group_5} -widget comboBox
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_AWUSER_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_WUSER_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_BUSER_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_ARUSER_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_RUSER_WIDTH" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_USER_VALUE" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_PROT_VALUE" -parent ${group_5}
  ipgui::add_param $IPINST -name "C_M_AXI_G_ACT_B_W_CACHE_VALUE" -parent ${group_5}



}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_PARAM1_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_PARAM1_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_PARAM1_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM1_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_PARAM1_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM1_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM1_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM1_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM1_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM1_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM1_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM1_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM1_CACHE_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_PARAM2_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_PARAM2_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_PARAM2_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_PARAM2_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_PARAM2_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_PARAM2_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_PARAM2_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM2_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM2_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM2_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM2_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_PARAM2_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_PARAM2_CACHE_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_R_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_R_CACHE_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_A_W_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_A_W_CACHE_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_R_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_R_CACHE_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_ENABLE_ID_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_ID_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_ID_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_DATA_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_DATA_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_ENABLE_USER_PORTS
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_AWUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_AWUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_WUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_WUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_BUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_BUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_ARUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_ARUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_RUSER_WIDTH when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH { PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_RUSER_WIDTH
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_USER_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_USER_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_PROT_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_PROT_VALUE
	return true
}

proc update_PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE } {
	# Procedure called to update C_M_AXI_G_ACT_B_W_CACHE_VALUE when any of the dependent parameters in the arguments change
}

proc validate_PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE { PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE } {
	# Procedure called to validate C_M_AXI_G_ACT_B_W_CACHE_VALUE
	return true
}


proc update_MODELPARAM_VALUE.C_S_AXI_CONTROL_ADDR_WIDTH { MODELPARAM_VALUE.C_S_AXI_CONTROL_ADDR_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	# WARNING: There is no corresponding user parameter named "C_S_AXI_CONTROL_ADDR_WIDTH". Setting updated value from the model parameter.
set_property value 8 ${MODELPARAM_VALUE.C_S_AXI_CONTROL_ADDR_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM1_CACHE_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_PARAM2_CACHE_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_R_CACHE_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_A_W_CACHE_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_R_CACHE_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ID_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_DATA_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_AWUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_ARUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_WUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_RUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_BUSER_WIDTH}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_USER_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_PROT_VALUE}
}

proc update_MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE { MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE } {
	# Procedure called to set VHDL generic/Verilog parameter value(s) based on TCL parameter value
	set_property value [get_property value ${PARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE}] ${MODELPARAM_VALUE.C_M_AXI_G_ACT_B_W_CACHE_VALUE}
}

