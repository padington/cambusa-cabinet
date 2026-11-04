// Round connector cabinet — design prototype v0.1, millimetres.
// Original geometry inspired by modular plywood joints; no source mesh copied.
// Assembly is a concept. Hinges, back fixings and load capacity need validation.
// Open in OpenSCAD; F5 = preview. Select part below for STL export with F6.

/* [Display] */
part = "assembly"; // [assembly,L,T,fit_test]
door_angle = 0; // [0:1:90]

/* [Cabinet] */
height = 1200;
width = 400;
depth = 350;
plywood = 15;
niche_clear_height = 287;

/* [Connector] */
diameter = 56;
connector_depth = 28;
face_thickness = 4;
clearance = 0.30; // Total slot allowance; not per side.
fixing_holes = false; // Optional 3.2 mm pilots in face. Validate screw choice.

/* [Hidden] */
$fn = 128;
eps = 0.02;
r = diameter/2;
left = r;
right = width-r;
bottom = r;
top = height-r;
divider = top-plywood-niche_clear_height;
side_lo = bottom-plywood/2;
side_hi = top+plywood/2;
inner_left = left+plywood/2;
inner_right = right-plywood/2;
board_front = face_thickness;
rear_face = depth-6;
board_back = rear_face-face_thickness;
door_lo = bottom+r+4;
door_hi = divider-r-4;

assert(plywood>0 && clearance>=0);
assert(diameter>2*plywood+12, "Increase connector diameter.");
assert(face_thickness>0 && connector_depth>face_thickness);
assert(width>diameter*2+plywood && divider>bottom+150);

module slot_profile(kind,s) {
    // Continuous side board; shelf butts against its inside face.
    translate([-s/2,kind=="T" ? -r-1 : -s/2])
        square([s,kind=="T" ? diameter+2 : r+1+s/2]);
    translate([s/2-0.2,-s/2]) square([r+1-s/2+0.2,s]);
}

module connector(kind="L",gap=clearance) {
    difference() {
        cylinder(d=diameter,h=connector_depth);
        translate([0,0,face_thickness])
            linear_extrude(connector_depth-face_thickness+1)
                slot_profile(kind,plywood+gap);
        if(fixing_holes)
            for(p=kind=="T" ? [[0,18],[0,-18],[18,0]] : [[0,18],[18,0]])
                translate([p[0],p[1],-eps]) cylinder(d=3.2,h=face_thickness+2*eps);
    }
}

module placed_connector(x,z,sx=1,sz=1,rear=false,kind="L") {
    multmatrix([[sx,0,0,x],[0,0,rear?-1:1,rear?rear_face:0],[0,sz,0,z],[0,0,0,1]])
        connector(kind);
}

module panel(x0,y0,z0,dx,dy,dz) {
    translate([x0,y0,z0]) cube([dx,dy,dz]);
}

module fascia(zlo,zhi,cz) {
    multmatrix([[1,0,0,0],[0,0,1,board_front],[0,1,0,0],[0,0,0,1]])
    linear_extrude(plywood)
    difference() {
        translate([inner_left,zlo]) square([inner_right-inner_left,zhi-zlo]);
        for(x=[left,right]) translate([x,cz]) circle(r=r+0.5);
    }
}

module moving_door() {
    translate([inner_left+2,board_front,0])
    rotate([0,0,-door_angle])
    translate([-inner_left-2,-board_front,0])
    difference() {
        panel(inner_left+2,board_front,door_lo,inner_right-inner_left-4,plywood,door_hi-door_lo);
        translate([inner_right-24,board_front+plywood+1,(door_lo+door_hi)/2])
            rotate([90,0,0]) cylinder(d=24,h=plywood+2);
    }
}

module assembly() {
    color([0.80,0.68,0.50]) {
        for(x=[left,right])
            panel(x-plywood/2,board_front,side_lo,plywood,board_back-board_front,side_hi-side_lo);
        for(z=[bottom,divider,top])
            panel(inner_left,board_front,z-plywood/2,inner_right-inner_left,board_back-board_front,plywood);
        // Removable inner shelf: conventional metal shelf pins.
        panel(inner_left+2,board_front+30,435,inner_right-inner_left-4,board_back-board_front-30,plywood);
        fascia(bottom+plywood/2,door_lo-2,bottom);
        fascia(door_hi+2,divider-plywood/2,divider);
        moving_door();
    }
    color([0.67,0.56,0.40]) {
        panel(left-plywood/2,rear_face,side_lo,right-left+plywood,6,side_hi-side_lo);
        // Back panel is 4 mm behind the board edges to clear the round caps.
        for(x=[left,right])
            for(span=[[bottom+r+4,divider-r-4],[divider+r+4,top-r-4]])
                panel(x-plywood/2,board_back,span[0],plywood,face_thickness,span[1]-span[0]);
        for(z=[bottom,divider,top])
            panel(left+r+4,board_back,z-plywood/2,right-left-2*r-8,face_thickness,plywood);
    }
    color([0.20,0.36,0.33])
        for(rear=[false,true]) for(side=[[left,1],[right,-1]]) {
            placed_connector(side[0],bottom,side[1],1,rear,"L");
            placed_connector(side[0],divider,side[1],1,rear,"T");
            placed_connector(side[0],top,side[1],-1,rear,"L");
        }
    // Metal hinge barrels and anti-tip brackets shown schematically.
    color([0.48,0.51,0.52]) {
        for(z=[210,690]) translate([inner_left+2,board_front,z-18]) cylinder(d=5,h=36,$fn=24);
        for(x=[width/4,width*3/4]) {
            panel(x-12,depth,top-59,24,2,34);
            panel(x-12,depth-18,top-59,24,20,2);
        }
    }
}

if(part=="assembly") assembly();
else if(part=="L") connector("L");
else if(part=="T") connector("T");
else if(part=="fit_test")
    difference() {
        cube([95,26,10]);
        for(i=[0:2])
            translate([[14,47.5,81][i]-(plywood+[0.15,0.30,0.45][i])/2,-1,2])
                cube([plywood+[0.15,0.30,0.45][i],28,9]);
    }
