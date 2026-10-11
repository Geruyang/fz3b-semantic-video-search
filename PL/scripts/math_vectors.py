"""Independent integer oracle: floor quotient + remainder comparison."""
from pathlib import Path
import random
root = Path(__file__).resolve().parents[1]
r = random.Random(20261010)
rows=[]
for shift in range(63):
    for v in [-(1<<47), -(1<<47)+1, -32767, -9,-7,-5,-3,-1,0,1,3,5,7,9,32767,(1<<47)-1]:
        for m in [-(1<<31),-3,-1,0,1,3,(1<<31)-1]:
            rows.append((v,m,shift))
for _ in range(2000): rows.append((r.randrange(-(1<<47),1<<47),r.randrange(-(1<<31),1<<31),r.randrange(63)))
with (root/'reports/math/vectors.txt').open('w') as f:
    for v,m,s in rows:
        q,rem=divmod(v*m,1<<s)
        q+=rem*2>(1<<s) or (rem*2==(1<<s) and q%2!=0)
        y=max(-32767,min(32767,q))
        f.write(f'{v & ((1<<48)-1):012x} {m & ((1<<32)-1):08x} {s:02x} {y&65535:04x}\n')
print(len(rows))
def table(i): return -(i//32%100)*2-100+(i%32)*3
with (root/'reports/math/gelu_vectors.txt').open('w') as f:
    for u in range(65536):
        q=u-32768
        folded=0 if q==0 else table(q+32768) if q<0 else q+table(32768-q)
        normal=0 if u<10003 else 32767 if u>=11020 else table(u-10000)
        f.write(f'{folded&65535:04x} {normal&65535:04x}\n')
def rounded_product(a,b,s):
    q,rem=divmod(a*b,1<<s)
    return q+(rem*2>(1<<s) or (rem*2==(1<<s) and q%2!=0))
narrow=[]
for shift in range(63):
    for a in [-32768,-32767,-9,-7,-5,-3,-1,0,1,3,5,7,9,32767]:
        for b in [-(1<<31),-3,-1,0,1,3,(1<<31)-1]:
            narrow.append((a,-a if a!=-32768 else 32767,b,b,shift,shift))
            narrow.append((a,a,b,-b if b!=-(1<<31) else (1<<31)-1,shift,(shift+17)%63))
for _ in range(3000):
    narrow.append((r.randrange(-32768,32768),r.randrange(-32768,32768),r.randrange(-(1<<31),1<<31),r.randrange(-(1<<31),1<<31),r.randrange(63),r.randrange(63)))
with (root/'reports/math/narrow_vectors.txt').open('w') as f:
    for a,b,om,rm,os,rs in narrow:
        y=max(-32767,min(32767,rounded_product(a,om,os)+rounded_product(b,rm,rs)))
        f.write(f'{a&65535:04x} {b&65535:04x} {om&((1<<32)-1):08x} {rm&((1<<32)-1):08x} {os:02x} {rs:02x} {y&65535:04x}\n')
print('narrow',len(narrow))
