/* IUSENTRA modification 2026-10-21. SPDX-License-Identifier: AGPL-3.0-only */
export function shapePath(kind, x1, y1, x2, y2) {
  if (![x1,y1,x2,y2].every(Number.isFinite)) throw new Error('Coordinate della forma non valide.');
  if(kind==='circle') {
    const side=Math.min(Math.abs(x2-x1),Math.abs(y2-y1));
    x2=x1+Math.sign(x2-x1)*side;y2=y1+Math.sign(y2-y1)*side;
  }
  const l=Math.min(x1,x2), r=Math.max(x1,x2), b=Math.min(y1,y2), t=Math.max(y1,y2);
  const cx=(l+r)/2, cy=(b+t)/2, rx=(r-l)/2, ry=(t-b)/2;
  if (Math.hypot(x2-x1,y2-y1)<3) return [];
  const poly=points=>[['M',...points[0]],...points.slice(1).map(p=>['L',...p]),['Z']];
  if (kind==='rectangle') return poly([[l,b],[r,b],[r,t],[l,t]]);
  if (kind==='triangle') return poly([[cx,t],[r,b],[l,b]]);
  if (kind==='diamond') return poly([[cx,t],[r,cy],[cx,b],[l,cy]]);
  if (kind==='ellipse'||kind==='circle') {
    const k=.5522847498307936;
    return [['M',r,cy],['C',r,cy+k*ry,cx+k*rx,t,cx,t],['C',cx-k*rx,t,l,cy+k*ry,l,cy],
      ['C',l,cy-k*ry,cx-k*rx,b,cx,b],['C',cx+k*rx,b,r,cy-k*ry,r,cy],['Z']];
  }
  if (kind==='line'||kind==='arrow'||kind==='double-arrow') {
    const commands=[['M',x1,y1],['L',x2,y2]];
    const head=(x,y,a)=>{const n=Math.min(14,Math.hypot(x2-x1,y2-y1)/3);commands.push(['M',x-n*Math.cos(a-.45),y-n*Math.sin(a-.45)],['L',x,y],['L',x-n*Math.cos(a+.45),y-n*Math.sin(a+.45)]);};
    const angle=Math.atan2(y2-y1,x2-x1);
    if(kind!=='line') head(x2,y2,angle);
    if(kind==='double-arrow') head(x1,y1,angle+Math.PI);
    return commands;
  }
  throw new Error('Forma non supportata.');
}
