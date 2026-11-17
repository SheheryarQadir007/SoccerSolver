#!/usr/bin/env bash
set -e

echo "================================================================="
echo "⚽ SoccerSolver - Autonomous Decision Engine & Scouting Optimizer"
echo "================================================================="

# Activate environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo -e "\n1. Running Problem Formulation & Mathematical Optimization (Any Position / Budget / Player):"
echo -e "Scenario A: Left-Back under 3M€ (LaLiga):"
python main.py solve "we need a left back under 3M€ who fits LaLiga"

echo -e "\nScenario B: High-Caliber Striker under 20M€ (Premier League):"
python main.py solve "striker under 20M for Premier League"

echo -e "\nScenario C: Player-Similarity Matching ('replacement for Pedri under 15M'):"
python main.py solve "replacement for Pedri under 15M"

echo -e "\n2. Running Historical Backtest (Season 2022/2023 Ground Truth):"
python main.py backtest --season 2022/2023 --position Left-Back --budget 3000000

echo -e "\n3. Simulating Proactive Event Trigger (Squad Injury at Getafe CF):"
python main.py trigger --event injury --club "Getafe CF" --injured "Diego Rico" --position Left-Back

echo -e "\n4. Reviewing Human-in-the-Loop Queue:"
python main.py queue list

echo -e "\n5. Observability Trace & Cost Log:"
python main.py logs

echo -e "\n================================================================="
echo "Demo complete! To launch the web Control Panel, run:"
echo "python main.py web"
echo "================================================================="
