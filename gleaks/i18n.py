"""Translation entry point; every user-visible string goes through ``_``."""

import gettext

gettext.textdomain("gleaks")
_ = gettext.gettext
ngettext = gettext.ngettext
