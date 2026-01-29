#!/bin/bash

# Stoic Practice Tracking Script

PRACTICE_LOG="/home/bengrady4/clawd/memory/stoic_practices.jsonl"
TEMPLATES="/home/bengrady4/clawd/memory/stoic_reflection_templates.json"

# Generate a random reflection prompt
get_random_prompt() {
    jq -r '.prompts[rand(.prompts | length)]' "$TEMPLATES"
}

# Log a practice entry
log_practice() {
    local practice_type="$1"
    local notes="$2"
    
    jq -n \
        --arg type "$practice_type" \
        --arg notes "$notes" \
        --arg timestamp "$(date -Iseconds)" \
        '{
            timestamp: $timestamp, 
            type: $type, 
            notes: $notes, 
            energy_level: "untracked"
        }' >> "$PRACTICE_LOG"
}

# Main interaction function
practice_prompt() {
    local prompt=$(get_random_prompt)
    echo "Stoic Moment: $prompt"
    read -p "Your reflection (press enter to skip): " response
    
    if [ -n "$response" ]; then
        log_practice "reflection" "$response"
        echo "Practice logged. Great job!"
    fi
}

# Run the prompt
practice_prompt