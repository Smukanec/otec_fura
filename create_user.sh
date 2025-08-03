#!/bin/bash
# Wrapper script to run the Python user creation utility.
# Passes all arguments through to scripts/create_user.py.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
python3 scripts/create_user.py "$@"
