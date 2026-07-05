#!/usr/bin/env bash
set -euo pipefail

curl -sS -X POST \
  "http://localhost:8004/proxy/gemini/v1beta/models/gemini-flash-lite-latest:generateContent" \
  -H "Authorization: Bearer lhqs_qAz9hXI_cjOCmoh_voFXuMsH6_xvsSBGoypZTyXwYww" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "你好，请用一句话介绍你自己"
          }
        ]
      }
    ],
    "generationConfig": {
      "temperature": 0.7,
      "maxOutputTokens": 200
    }
  }'
