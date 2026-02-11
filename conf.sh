#!/bin/bash
clear
cat << EOF
Chatterbox TTS

This will configure the Chatterbox TTS (Text-to-Speech) service.

Chatterbox is an optimized fork of XTTS with faster inference and improved performance.

Options:
* GPU = Uses GPU acceleration for faster inference. Recommended for NVIDIA cards.
* CPU = Runs on CPU only. Use this for AMD cards or systems without GPU support.

Recommended to use GPU if you have an NVIDIA GPU.

EOF

if [ ! -d /home/dwemer/chatterbox ]; then
        echo "Error: Chatterbox not installed"
        exit 1
fi

echo "Select an option from the list:"
echo
echo "1. Enable service (GPU)"
echo "2. Enable service (CPU)"
echo "0. Disable service"
echo

# Prompt the user to make a selection
read -p "Select an option by picking the matching number: " selection

# Validate the input

if [ "$selection" -eq "0" ]; then
    echo "Disabling service. Run this again to enable it"
    rm /home/dwemer/chatterbox/start.sh &>/dev/null
    exit 0
fi

if [ "$selection" -eq "1" ]; then
    ln -sf /home/dwemer/chatterbox/start-gpu.sh /home/dwemer/chatterbox/start.sh
    echo "✓ Chatterbox enabled with GPU acceleration"
    exit 0
fi

if [ "$selection" -eq "2" ]; then
    ln -sf /home/dwemer/chatterbox/start-cpu.sh /home/dwemer/chatterbox/start.sh
    echo "✓ Chatterbox enabled with CPU mode"
    exit 0
fi

echo "Invalid selection."
exit 1

