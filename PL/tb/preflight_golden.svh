// Generated independently from frozen C++ headers; never imports DUT package.
function automatic integer channels(input integer p); case(p) 0:return 128;1:return 256;2:return 64;3:return 64; default:return 0;endcase endfunction
function automatic integer stride(input integer p); case(p) 0:return 21081;1:return 59705;2:return 10985;3:return 11280; default:return 0;endcase endfunction
function automatic integer bias_offset(input integer p); case(p) 0:return 928;1:return 1856;2:return 464;3:return 464; default:return 0;endcase endfunction
function automatic integer gelu_offset(input integer p); case(p) 0:return 1761;1:return 3521;2:return 881;3:return 881; default:return 0;endcase endfunction
function automatic integer slot_words_for(input integer p); case(p) 0:return 16384;1:return 8192;2:return 32768;3:return 32768; default:return 0;endcase endfunction
function automatic integer gelu_zero(input integer p,b);case(p)
0:case(b)0:return 15136;1:return 7424;2:return 7109;3:return 1949;4:return 0;5:return 0;6:return 2420;7:return 0;8:return 0;9:return 6159;10:return 4602;11:return 25501; default:return 0;endcase
1:case(b)0:return 1756;1:return 4433;2:return 6077;3:return 6559;4:return 8485;5:return 10116;6:return 9466;7:return 11635;8:return 8084;9:return 5675;10:return 0;11:return 292;12:return 4914;13:return 13445;14:return 11670;15:return 17357;16:return 19327;17:return 18908;18:return 19032;19:return 19136; default:return 0;endcase
2:case(b)0:return 25496;1:return 16299;2:return 13211;3:return 17193; default:return 0;endcase
default:return 0;endcase endfunction
function automatic integer gelu_tail(input integer p,b);case(p)
0:case(b)0:return 52936;1:return 48646;2:return 48845;3:return 53151;4:return 49881;5:return 48536;6:return 47407;7:return 53999;8:return 50477;9:return 45132;10:return 49941;11:return 38148; default:return 0;endcase
1:case(b)0:return 48704;1:return 51761;2:return 54883;3:return 52628;4:return 53218;5:return 49106;6:return 50628;7:return 56097;8:return 53282;9:return 48134;10:return 56252;11:return 53479;12:return 56320;13:return 57196;14:return 50287;15:return 50325;16:return 51714;17:return 52132;18:return 59373;19:return 61454; default:return 0;endcase
2:case(b)0:return 50236;1:return 55552;2:return 49509;3:return 52328; default:return 0;endcase
default:return 0;endcase endfunction
function automatic integer gold_start(input integer job);case(job)0:return 0;1:return 3120;2:return 9080;3:return 10048;4:return 10310;5:return 10570;6:return 10830;7:return 11090;8:return 11350;9:return 11648;10:return 11890;11:return 12150;12:return 12392;13:return 12634;14:return 12896;15:return 13158;16:return 13420;17:return 13682;18:return 13682;19:return 13682;20:return 13682;21:return 13682;22:return 13682;23:return 13682;24:return 13682;default:return -1;endcase endfunction
function automatic integer gold_end(input integer job);case(job)0:return 3120;1:return 9080;2:return 10048;3:return 10310;4:return 10570;5:return 10830;6:return 11090;7:return 11350;8:return 11648;9:return 11890;10:return 12150;11:return 12392;12:return 12634;13:return 12896;14:return 13158;15:return 13420;16:return 13682;17:return 13682;18:return 13682;19:return 13682;20:return 13682;21:return 13682;22:return 13682;23:return 13682;24:return 13942;default:return -1;endcase endfunction
function automatic integer gold_beats(input integer job);case(job)0:return 99000;1:return 189320;2:return 30568;3:return 8384;4:return 8250;5:return 8250;6:return 8250;7:return 8250;8:return 9466;9:return 7642;10:return 8250;11:return 7642;12:return 7642;13:return 8384;14:return 8384;15:return 8384;16:return 8384;17:return 0;18:return 0;19:return 0;20:return 0;21:return 0;22:return 0;23:return 0;24:return 8250;default:return -1;endcase endfunction
