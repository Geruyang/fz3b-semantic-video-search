"""CPU target/PLL plan; UG1085 v2.5 Table 37-2, pp.1140-1141."""
REFERENCE_HZ=33333333
MIN_KHZ,MAX_KHZ=600000,1200000
TARGETS=(600000,800000,1000000,1200000)
DPLL_TARGETS=(600000,1200000)


def validate_khz(value):
    if type(value) is not int:
        raise ValueError('CPU target must be integer kHz')
    value={599999:600000,1199999:1200000}.get(value,value)
    if value not in TARGETS:
        raise ValueError('CPU target must be 600/800/1000/1200MHz')
    return value


def fractional_cfg(fbdiv):
    if not 45<=fbdiv<=89:
        raise ValueError('FBDIV outside qualified CPU plan')
    lock={45:825,46:800,47:775,48:775,49:750,50:750,51:725,
          52:700,53:700,54:675,55:675,56:650,57:650,58:625,59:625,60:625}.get(fbdiv,600)
    resistance=1 if fbdiv<=47 else 6 if fbdiv<=65 else 10 if fbdiv<=81 else 6 if fbdiv<=87 else 12
    return dict(cp=3,res=resistance,lfhf=3,lock_delay=63,lock_count=lock)


def pll_plan(khz):
    khz=validate_khz(khz)
    if khz in (600000,1200000):
        divider=2 if khz==600000 else 1
        return dict(khz=khz,parent=2,divider=divider,actual_hz=1199999988//divider,restore_vpll=True)
    fbdiv=48 if khz==800000 else 60
    vco=REFERENCE_HZ*fbdiv
    params=[1,fbdiv,0,0,0,63,775 if fbdiv==48 else 625,3,3,2]
    return dict(khz=khz,parent=3,divider=1,fbdiv=fbdiv,frac=0,
                vco_hz=vco,actual_hz=vco//2,generic_mode=1,params=params)
