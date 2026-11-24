from fc.core import Finding
from fc.gx.core import gx_rule


@gx_rule('G15', 'DXF unit header contradicts the drawing (sizes only make sense in another unit)')
def check(g):
    """The file says metres (or inches) but the parts are furniture-sized only in mm (or the other way round).
    Imported as declared, CAM scales every part by 1000x or 25.4x. A warning, not an error: the operator sets the
    import units in CAM and sees a 2 km sheet at once - but it must be fixed before the file is shared."""
    if getattr(g, 'units_declared', None):
        yield Finding('G15', 'warn', 'unit header says %s, but the drawing is %s-sized: set the import units by hand'
                      % (g.units_declared, g.units.rstrip('?')), '')
