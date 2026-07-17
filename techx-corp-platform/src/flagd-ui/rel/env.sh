#!/bin/sh

# Release environment configuration
# This file is copied into the release by mix release.

export RELEASE_DISTRIBUTION=name
export RELEASE_NODE=${RELEASE_NODE:-"flagd_ui@127.0.0.1"}
