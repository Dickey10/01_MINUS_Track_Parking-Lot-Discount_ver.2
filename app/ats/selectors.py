# ATS selector map. Update this file first if the ATS HTML changes.

LOGIN_URL = "/login"
DISCOUNT_URL = "/discount/registration"

CAR_SEARCH_INPUT = "#schCarNo"
SEARCH_BUTTON = "input.btnS1_1"
CAR_GRID = "#gridMst"
DISCOUNT_CODES_DIV = "#div_dscntcodes"

DISCOUNT_30MIN_SEL = '#div_dscntcodes a[name="btnDscntType"][time="30"]'
DISCOUNT_60MIN_SEL = '#div_dscntcodes a[name="btnDscntType"][time="60"]'

# These are fallbacks only. ATS may render Korean messages; registrar.py checks
# several possible labels and does not depend on these exact strings alone.
SUCCESS_MESSAGE = "registered"
NO_RESULT_MESSAGE = "no result"

