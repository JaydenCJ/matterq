"""Allow ``python -m matterq`` as an alias for the ``matterq`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
