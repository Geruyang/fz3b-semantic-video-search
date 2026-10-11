package cnn_profile_pkg;
 function automatic int unsigned channels(input int unsigned p); return p==0?128:p==1?256:64; endfunction
 function automatic int unsigned width(input int unsigned p); return p==0?32:p==1?16:64; endfunction
 function automatic int unsigned max_blocks(input int unsigned p); return p==0?12:p==1?20:p==2?4:1; endfunction
 function automatic int unsigned stride(input int unsigned p); return p==0?21081:p==1?59705:p==2?10985:11280; endfunction
 function automatic int unsigned slot_words_for(input int unsigned p); return p==0?16384:p==1?8192:32768; endfunction
 function automatic int unsigned bias_offset(input int unsigned p); return p==0?928:p==1?1856:464; endfunction
 function automatic int unsigned gelu_offset(input int unsigned p); return p==0?1761:p==1?3521:881; endfunction
 function automatic int unsigned gelu_zero(input int unsigned p,b);
  case(p)
   0: case(b) 0:return 15136;1:return 7424;2:return 7109;3:return 1949;4:return 0;5:return 0;6:return 2420;7:return 0;8:return 0;9:return 6159;10:return 4602;11:return 25501;default:return 0;endcase
   1: case(b) 0:return 1756;1:return 4433;2:return 6077;3:return 6559;4:return 8485;5:return 10116;6:return 9466;7:return 11635;8:return 8084;9:return 5675;10:return 0;11:return 292;12:return 4914;13:return 13445;14:return 11670;15:return 17357;16:return 19327;17:return 18908;18:return 19032;19:return 19136;default:return 0;endcase
   2: case(b) 0:return 25496;1:return 16299;2:return 13211;3:return 17193;default:return 0;endcase
   default:return 0;
  endcase
 endfunction
 function automatic int unsigned gelu_tail(input int unsigned p,b);
  case(p)
   0: case(b) 0:return 52936;1:return 48646;2:return 48845;3:return 53151;4:return 49881;5:return 48536;6:return 47407;7:return 53999;8:return 50477;9:return 45132;10:return 49941;11:return 38148;default:return 0;endcase
   1: case(b) 0:return 48704;1:return 51761;2:return 54883;3:return 52628;4:return 53218;5:return 49106;6:return 50628;7:return 56097;8:return 53282;9:return 48134;10:return 56252;11:return 53479;12:return 56320;13:return 57196;14:return 50287;15:return 50325;16:return 51714;17:return 52132;18:return 59373;19:return 61454;default:return 0;endcase
   2: case(b) 0:return 50236;1:return 55552;2:return 49509;3:return 52328;default:return 0;endcase
   default:return 0;
  endcase
 endfunction
 // Legal configurations form a 37-entry exact constant map; no variable DSP multiply.
 function automatic int unsigned expected_param_words(input int unsigned p,b);
  case(p)
   0:case(b)1:return 21081;2:return 42162;3:return 63243;4:return 84324;5:return 105405;6:return 126486;7:return 147567;8:return 168648;9:return 189729;10:return 210810;11:return 231891;12:return 252972;default:return 0;endcase
   1:case(b)1:return 59705;2:return 119410;3:return 179115;4:return 238820;5:return 298525;6:return 358230;7:return 417935;8:return 477640;9:return 537345;10:return 597050;11:return 656755;12:return 716460;13:return 776165;14:return 835870;15:return 895575;16:return 955280;17:return 1014985;18:return 1074690;19:return 1134395;20:return 1194100;default:return 0;endcase
   2:case(b)1:return 10985;2:return 21970;3:return 32955;4:return 43940;default:return 0;endcase
   3:case(b)1:return 11280;default:return 0;endcase
   default:return 0;
  endcase
 endfunction
endpackage
