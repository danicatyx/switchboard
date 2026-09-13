"""python -m switchboard.sync — pull CODEOWNERS, catalog and deploy history from GitHub."""
import sys

from dotenv import load_dotenv

from .integrations.github import GitHubAdapter

load_dotenv()

if __name__ == "__main__":
    gh = GitHubAdapter()
    if not gh.live:
        print("GITHUB_TOKEN and GITHUB_REPO are required (see .env.example)", file=sys.stderr)
        sys.exit(2)
    gh.sync()
