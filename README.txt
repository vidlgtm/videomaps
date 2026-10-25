videomaps - the map-history FILM FACTORY
=========================================
factory/          THE FACTORY (start here: factory/README.txt). An order goes in, a finished film comes out.
                  director/ (automatic director), station/ (processing station), engine/ (Remotion renderer),
                  rules/ (fixed identity), order/ORDER_SPEC.txt (what the brain delivers), orders/<film>/ (one folder per film)
.github/workflows/factory.yml   the factory's production line (started by workflow_dispatch only)
production/       shared tools the factory calls (terrain / HD tiles, sound effects, Blender, CI helpers)
reference/ussr15/ hand-made scene sources of our film v5 (the quality reference)
assets/, fonts/   house music, sound effects and fonts (OFL licences next to each font)
projects/example_baltic/   small example from the old kit era (kept for its voice takes)
Releases: factory_* = factory results; all other releases are protected production assets (never delete).
