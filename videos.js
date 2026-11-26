// Video library. Each: id, title, system (must match a system name in BP), file, poster, minutes, description, key points.
// Videos are original animations made with tools/videos (render.py draws frames, narrate.py adds the voice).
var VIDS=[
{id:"cardiac-ap",title:"The cardiac action potential",system:"Cardiovascular",file:"videos/cardiac-action-potential.mp4",poster:"videos/cardiac-action-potential.jpg",mins:"3:14",
desc:"Watch the ion channels open phase by phase in a ventricular muscle cell and an SA node pacemaker cell, with the voltage traced as it happens.",
pts:["Ventricular cell: phase 4 rest at −90 mV (IK1), phase 0 fast Na⁺ in, phase 1 transient K⁺ out, phase 2 plateau (L-type Ca²⁺ in, K⁺ out), phase 3 K⁺ out.","The long effective refractory period prevents tetanic contraction.","Pacemaker cell: phase 4 drifts up (funny current If, then T-type Ca²⁺), phase 0 is L-type Ca²⁺, no phases 1 or 2.","Sympathetic input steepens phase 4 (faster rate); vagal input flattens it (slower rate).","Drugs: class I block Na⁺, class III block K⁺ (long QT), class IV and ivabradine slow the SA node."]}
];
