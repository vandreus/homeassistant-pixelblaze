"""Constants for the Pixelblaze integration."""

DOMAIN = "pixelblaze"

CONF_POLL_INTERVAL = "poll_interval"
CONF_DYNAMIC_VARS = "dynamic_vars"

DEFAULT_POLL_INTERVAL = 5
DEFAULT_DYNAMIC_VARS = True

PLATFORMS = ["light", "number", "select", "sensor", "switch"]

# Exported pattern variables that are read-only game state, exposed as sensors.
READONLY_VARS = {"score", "lives", "level", "lines", "over", "won", "alive", "fps"}

# Exported variables that are edge-trigger counters (button presses), not
# meaningful as entities. Matches cL, cR, cRot, cDown, cDrop, cNew, ...
COUNTER_VAR_PREFIX = "c"

SERVICE_SET_VARS = "set_vars"
SERVICE_SET_PATTERN = "set_pattern"

MANUFACTURER = "ElectroMage"
MODEL = "Pixelblaze"
