#!/usr/bin/env python3
"""
Quick tournament runner for testing.

Usage:
    python scripts/run_tournament.py [--bots tactical,aggressive,defensive,random]
"""
import argparse
import time
import sys

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run a quick Fleet Commander tournament")
    parser.add_argument(
        "--bots",
        default="tactical,aggressive,defensive,random",
        help="Comma-separated list of bots to include"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="Server URL"
    )
    parser.add_argument(
        "--name",
        default="Quick Tournament",
        help="Tournament name"
    )
    args = parser.parse_args()

    bots = [b.strip() for b in args.bots.split(",")]
    base_url = args.server.rstrip("/")

    print(f"Creating tournament with bots: {', '.join(bots)}")
    print()

    # Create tournament
    try:
        r = requests.post(
            f"{base_url}/api/fleet-commander/tournaments",
            json={
                "name": args.name,
                "include_bots": bots,
            },
            timeout=10,
        )
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to {base_url}")
        print("Make sure the backend is running (make run-backend)")
        sys.exit(1)

    tournament = r.json()["tournament"]
    tid = tournament["id"]
    print(f"Created tournament: {tid}")
    print(f"Participants: {', '.join(p['name'] for p in tournament['participants'])}")
    print()

    # Start tournament
    r = requests.post(f"{base_url}/api/fleet-commander/tournaments/{tid}/run")
    print("Tournament running...")
    print()

    # Poll for completion
    max_wait = 120  # 2 minutes max
    start_time = time.time()

    while time.time() - start_time < max_wait:
        time.sleep(2)

        r = requests.get(f"{base_url}/api/fleet-commander/tournaments/{tid}")
        tournament = r.json()["tournament"]

        # Show current match if any
        current = tournament.get("current_match")
        if current and current.get("state") == "in_progress":
            p1_name = next(
                (p["name"] for p in tournament["participants"] if p["id"] == current["player1_id"]),
                "?"
            )
            p2_name = next(
                (p["name"] for p in tournament["participants"] if p["id"] == current["player2_id"]),
                "?"
            )
            print(f"  Match: {p1_name} vs {p2_name}...", end="\r")

        if tournament["state"] == "completed":
            break

    print()
    print("=" * 50)
    print(f"Tournament: {tournament['name']}")
    print(f"Status: {tournament['state']}")
    print("=" * 50)
    print()
    print("Final Standings:")
    print("-" * 40)

    for i, standing in enumerate(tournament["standings"]):
        participant = next(
            (p for p in tournament["participants"] if p["id"] == standing["participant_id"]),
            {"name": "?"}
        )
        name = participant["name"]
        wins = standing["wins"]
        losses = standing["losses"]
        points = standing["points"]
        ships_destroyed = standing.get("ships_destroyed", 0)

        medal = ""
        if i == 0:
            medal = "🥇 "
        elif i == 1:
            medal = "🥈 "
        elif i == 2:
            medal = "🥉 "

        print(f"  {medal}{i+1}. {name}: {wins}W-{losses}L ({points} pts) - {ships_destroyed} ships destroyed")

    print()

    # Show match history
    print("Matches:")
    print("-" * 40)
    for match in tournament["matches"]:
        if match["state"] != "completed":
            continue

        p1_name = next(
            (p["name"] for p in tournament["participants"] if p["id"] == match["player1_id"]),
            "?"
        )
        p2_name = next(
            (p["name"] for p in tournament["participants"] if p["id"] == match["player2_id"]),
            "?"
        )

        result = match.get("result", {})
        winner_id = result.get("winner_id")
        winner_name = next(
            (p["name"] for p in tournament["participants"] if p["id"] == winner_id),
            "?"
        )
        turns = result.get("turns", 0)

        print(f"  {p1_name} vs {p2_name}: {winner_name} wins ({turns} turns)")

    print()


if __name__ == "__main__":
    main()
