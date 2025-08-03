#!/bin/bash
# Wrapper script to run the Python user creation utility.
# Passes all arguments through to scripts/create_user.py.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/scripts/create_user.py" "$@"
