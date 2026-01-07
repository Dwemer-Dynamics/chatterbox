#!/bin/bash

if [ ! -d /home/dwemer/chatterbox ]; then
        exit "chatterbox not installed"
fi

mapfile -t files < <(find /home/dwemer/chatterbox/ -name "start-*.sh")
# Check if any files were found

if [ ${#files[@]} -eq 0 ]; then
    echo "No files found matching the pattern."
    exit 1
fi

# Display the files in a numbered list
echo -e "Select a an option from the list:\n\n"
for i in "${!files[@]}"; do
    echo "$((i+1)). ${files[$i]}"
done

echo "0. Disable service";
echo

# Prompt the user to make a selection
read -p "Select an option by picking the matching number: " selection

# Validate the input

if [ "$selection" -eq "0" ]; then
    echo "Disabling service. Run this again to enable"
    rm /home/dwemer/chatterbox/start.sh &>/dev/null
    exit 0
fi

if ! [[ "$selection" =~ ^[0-9]+$ ]] || [ "$selection" -lt 1 ] || [ "$selection" -gt ${#files[@]} ]; then
    echo "Invalid selection."
    exit 1
fi

# Get the selected file
selected_file="${files[$((selection-1))]}"

echo "You selected: $selected_file"

ln -sf $selected_file /home/dwemer/chatterbox/start.sh


# Ensure all start scripts are executable
chmod +x /home/dwemer/xtts-api-server/start-*.sh 2>/dev/null || true
