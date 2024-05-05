#!/bin/bash
virtualenv myenv

source myenv/bin/activate

pip install -r req.txt

# Prompt user to install ngrok
echo "Please install ngrok using link https://ngrok.com/download"

# Once installed run the command ngrok http 2000
echo "Run Command 'ngrok http 2000'"
