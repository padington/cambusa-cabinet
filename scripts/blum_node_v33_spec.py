"""One source of dimensions for the v33 solid, CNC contours and inspection."""
VERSION='cambusa-v33-independent-hinge'
CUP_DIAMETER=35.2
CUP_DEPTH=11.2
PILOT_DIAMETER=2.7
PILOT_DEPTH=8.0
RELIEF_WIDTH=11.0
RELIEF_HEIGHT=28.0
RELIEF_DEPTH=6.0
RELIEF_RADIUS=3.0
RELIEF_OVERRUN=3.0
NATIVE_HINGE_EDGE_X=7.0
TARGET_MOVING_LINK_CLEARANCE=.5


def native_relief_bounds():
    return (NATIVE_HINGE_EDGE_X-RELIEF_WIDTH,
            NATIVE_HINGE_EDGE_X+RELIEF_OVERRUN)


def native_door(pockets=True):
    import cadquery as cq
    from check_full_blum_node import box
    door=box([-445,-56.5,-482],[7,-38.5,482])
    door=door.cut(cq.Solid.makeCylinder(CUP_DIAMETER/2,CUP_DEPTH,cq.Vector(-16,-38.5,0),cq.Vector(0,-1,0)))
    for z in (-22.5,22.5):
        door=door.cut(cq.Solid.makeCylinder(PILOT_DIAMETER/2,PILOT_DEPTH,cq.Vector(-25.5,-38.5,z),cq.Vector(0,-1,0)))
    if pockets:
        lo,hi=native_relief_bounds()
        pocket=cq.Workplane().box(hi-lo,RELIEF_DEPTH,RELIEF_HEIGHT).edges('|Y').fillet(RELIEF_RADIUS)
        pocket=pocket.translate(((lo+hi)/2,-38.5-RELIEF_DEPTH/2,0)).val()
        door=door.cut(pocket)
    return door
