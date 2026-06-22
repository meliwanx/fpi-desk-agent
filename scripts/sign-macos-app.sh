#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:?usage: scripts/sign-macos-app.sh APP_PATH SIGNING_IDENTITY}"
SIGNING_IDENTITY="${2:?usage: scripts/sign-macos-app.sh APP_PATH SIGNING_IDENTITY}"
APP_CONTENTS="$APP_PATH/Contents"
BUNDLE_BACKEND="$APP_CONTENTS/Resources/backend"

if [ ! -d "$APP_PATH" ]; then
  echo "::error::app bundle not found: $APP_PATH"
  exit 1
fi

is_macho() {
  [ -f "$1" ] && file "$1" | grep -q "Mach-O"
}

remove_signature() {
  codesign --remove-signature "$1" >/dev/null 2>&1 || true
}

remove_bundle_signature_artifacts() {
  local bundle="$1"
  rm -rf \
    "$bundle/Contents/_CodeSignature" \
    "$bundle/_CodeSignature" \
    "$bundle/Versions/Current/_CodeSignature" \
    "$bundle/Versions/"*/_CodeSignature
}

verify_signature() {
  local target="$1"
  local details
  if ! details=$(codesign -dv --verbose=4 "$target" 2>&1); then
    echo "::error file=$target::codesign details failed"
    echo "$details"
    return 1
  fi
  if ! grep -q "Authority=Developer ID Application" <<<"$details"; then
    echo "::error file=$target::missing Developer ID Application authority"
    echo "$details"
    return 1
  fi
  if ! grep -q "Timestamp=" <<<"$details"; then
    echo "::error file=$target::missing secure timestamp"
    echo "$details"
    return 1
  fi
}

verify_macho_signature() {
  local binary="$1"
  local verify_output
  if ! verify_output=$(codesign --verify --strict --verbose=4 "$binary" 2>&1); then
    echo "::error file=$binary::codesign strict verification failed"
    echo "$verify_output"
    return 1
  fi
  verify_signature "$binary"
}

verify_bundle_signature() {
  local bundle="$1"
  local verify_output
  if ! verify_output=$(codesign --verify --strict --verbose=4 "$bundle" 2>&1); then
    echo "::error file=$bundle::codesign strict verification failed"
    echo "$verify_output"
    return 1
  fi
  verify_signature "$bundle"
}

sign_macho() {
  local binary="$1"
  local attempt
  remove_signature "$binary"
  for attempt in 1 2 3; do
    if codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$binary" \
      && verify_macho_signature "$binary"; then
      return 0
    fi
    echo "Retrying Developer ID signing for $binary (attempt $attempt failed)"
    remove_signature "$binary"
    sleep 2
  done
  echo "::error file=$binary::failed to produce Developer ID signature with secure timestamp"
  verify_macho_signature "$binary"
}

sign_bundle() {
  local bundle="$1"
  local attempt
  for attempt in 1 2 3; do
    remove_bundle_signature_artifacts "$bundle"
    remove_signature "$bundle"
    if codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$bundle" \
      && verify_bundle_signature "$bundle"; then
      return 0
    fi
    echo "Retrying Developer ID signing for bundle $bundle (attempt $attempt failed)"
    sleep 2
  done
  echo "::error file=$bundle::failed to produce bundle signature with stable resource seal"
  verify_bundle_signature "$bundle"
}

restore_python_framework_symlinks() {
  local fw_path="$BUNDLE_BACKEND/_internal/Python.framework"
  if [ ! -d "$fw_path" ]; then
    return 0
  fi

  rm -rf "$fw_path/_CodeSignature"
  if [ -f "$fw_path/Python" ] && [ ! -L "$fw_path/Python" ]; then
    rm "$fw_path/Python"
    if [ ! -L "$fw_path/Versions/Current" ]; then
      (cd "$fw_path/Versions" && ln -s 3.12 Current)
    fi
    ln -s Versions/Current/Python "$fw_path/Python"
  fi

  local python_bin="$BUNDLE_BACKEND/_internal/Python"
  if [ -f "$python_bin" ] && [ ! -L "$python_bin" ]; then
    rm "$python_bin"
    ln -s Python.framework/Versions/Current/Python "$python_bin"
  fi
}

restore_python_framework_symlinks

macho_list="$(mktemp)"
framework_list="$(mktemp)"
trap 'rm -f "$macho_list" "$framework_list"' EXIT

find "$APP_CONTENTS" -type f -print0 | while IFS= read -r -d '' binary; do
  if is_macho "$binary"; then
    printf '%s\0' "$binary" >>"$macho_list"
  fi
done

find "$APP_CONTENTS" -type d -name "*.framework" -print0 >"$framework_list"

macho_count=$(tr -cd '\0' <"$macho_list" | wc -c | tr -d ' ')
framework_count=$(tr -cd '\0' <"$framework_list" | wc -c | tr -d ' ')
echo "Signing $macho_count Mach-O files and $framework_count frameworks in $APP_PATH"

while IFS= read -r -d '' binary; do
  sign_macho "$binary"
done <"$macho_list"

while IFS= read -r -d '' framework; do
  sign_bundle "$framework"
done <"$framework_list"

sign_bundle "$APP_PATH"

echo "Verifying nested Mach-O signatures after outer app signing"
while IFS= read -r -d '' binary; do
  verify_macho_signature "$binary"
done <"$macho_list"

while IFS= read -r -d '' framework; do
  verify_bundle_signature "$framework"
done <"$framework_list"

verify_bundle_signature "$APP_PATH"
