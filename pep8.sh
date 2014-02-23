#!/bin/sh

# Run autpep8 to make the code PEP8 complient. 
# Ignore E303 because 1 blank line between methods is not enough. 
# I don't have to agree with everything Van Rossum says. 
autopep8 --in-place --aggressive "scraper/$1" --ignore E303


