import argparse
import re
import subprocess  # noqa: S404
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from urllib.parse import quote


@dataclass
class ConventionalCommit:
    """
    A structured representation of a conventional commit with enhanced metadata processing.

    Parameters
    ----------
    hash : str
        The Git commit hash identifier
    prefix : str
        The conventional commit prefix (e.g., 'cfp', 'conf')
    message : str
        The commit message content without the prefix
    author : str
        The commit author's name
    date : datetime
        The commit timestamp

    Methods
    -------
    generate_url
        Generates a formatted URL for the conference entry
    to_markdown
        Converts the commit to a markdown-formatted string
    """

    hash: str
    prefix: str
    message: str
    author: str
    date: datetime

    def generate_url(self) -> str:
        """
        Generate a formatted URL for the conference entry.

        Returns
        -------
        str
            Formatted URL with sanitized conference title

        Notes
        -----
        Implements URL sanitization for conference titles
        """
        # Basic URL-safe transformation of the message
        sanitized = quote(self.message.lower().replace(" ", "-"))
        return f"https://pythondeadlin.es/conference/{sanitized}"

    def to_markdown(self) -> str:
        """
        Convert the commit to a markdown-formatted string.

        Returns
        -------
        str
            Markdown-formatted commit representation

        Notes
        -----
        Formats the entry with date, message, and URL
        """
        date_str = self.date.strftime("%Y-%m-%d")
        return f"- [{date_str}] [{self.message}]({self.generate_url()})"


class GitCommitParser:
    """
    Analyzes git repository history for conference-related commits with markdown output capabilities.

    Parameters
    ----------
    repo_path : str, optional
        Path to the git repository, by default "."
    prefixes : List[str], optional
        List of commit prefixes to search for, by default ["cfp", "conf"]
    days : int, optional
        Number of days to look back in history, by default None
    """

    def __init__(self, repo_path: str = ".", prefixes: list[str] | None = None, days: int | None = None):
        self.repo_path = repo_path
        self.prefixes = prefixes or ["cfp", "conf"]
        self.days = days
        self._prefix_pattern = re.compile(rf'^({"|".join(map(re.escape, self.prefixes))}):\s*(.+)$', re.IGNORECASE)

    def _execute_git_command(self, command: list[str]) -> str:
        """Implementation remains unchanged."""
        try:
            result = subprocess.run(
                ["git", *command],  # noqa: S603, S607
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error executing git command: {e}")
            raise

    def parse_commit_message(
        self,
        commit_hash: str,
        message: str,
        author: str,
        date_str: str,
    ) -> ConventionalCommit | None:
        """Implementation remains unchanged."""
        match = self._prefix_pattern.match(message.strip())
        if not match:
            return None

        prefix, content = match.groups()
        date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")

        return ConventionalCommit(hash=commit_hash, prefix=prefix.lower(), message=content, author=author, date=date)

    def get_conventional_commits(self) -> list[ConventionalCommit]:
        """Implementation remains unchanged."""
        git_log_format = "--pretty=format:%H%n%s%n%an%n%ai"
        git_command = ["log", git_log_format]

        if self.days is not None:
            since_date = datetime.now(timezone.utc) - timedelta(days=self.days)
            git_command.extend(["--since", since_date.strftime("%Y-%m-%d")])

        log_output = self._execute_git_command(git_command)

        commits = []
        current_commit = []

        for line in log_output.split("\n"):
            if line:
                current_commit.append(line)

            if len(current_commit) == 4:
                commit = self.parse_commit_message(*current_commit)
                if commit:
                    commits.append(commit)
                current_commit = []

        return commits

    def _generate_link_list(self, commits: list[ConventionalCommit]) -> str:
        """
        Generate a comma-separated list of markdown-formatted links.

        Parameters
        ----------
        commits : List[ConventionalCommit]
            List of commits to format

        Returns
        -------
        str
            Formatted link list

        Notes
        -----
        Implements Oxford comma formatting for lists with more than two items
        """
        if not commits:
            return ""

        links = [f"[{commit.message}]({commit.generate_url()})" for commit in commits]

        if len(links) == 1:
            return links[0]
        if len(links) == 2:
            return f"{links[0]} and {links[1]}"
        return f"{', '.join(links[:-1])}, and {links[-1]}"

    def generate_markdown_report(self) -> str:
        """
        Generate a markdown-formatted report of commits grouped by type.

        Returns
        -------
        str
            Complete markdown-formatted report

        Notes
        -----
        Organizes commits by type (cfp/conf) with chronological ordering and
        includes a comprehensive summary sentence
        """
        commits = self.get_conventional_commits()
        grouped_commits: dict[str, list[ConventionalCommit]] = defaultdict(list)

        for commit in commits:
            grouped_commits[commit.prefix].append(commit)

        # Sort commits within each group by date
        for commits_list in grouped_commits.values():
            commits_list.sort(key=lambda x: x.date, reverse=True)

        # Generate markdown sections
        sections = []

        if grouped_commits.get("cfp"):
            sections.extend(
                ["## Call for Papers", "", *[commit.to_markdown() for commit in grouped_commits["cfp"]], ""],
            )

        if grouped_commits.get("conf"):
            sections.extend(["## Conferences", "", *[commit.to_markdown() for commit in grouped_commits["conf"]], ""])

        # Generate summary sentence
        conf_links = self._generate_link_list(grouped_commits.get("conf", []))
        cfp_links = self._generate_link_list(grouped_commits.get("cfp", []))

        summary_parts = []
        if conf_links:
            summary_parts.append(f"these conferences {conf_links}")
        if cfp_links:
            summary_parts.append(f"new CFPs for {cfp_links}")

        if summary_parts:
            sections.extend(["## Summary", "", f"I found {' and '.join(summary_parts)}.", ""])

        return "\n".join(sections)


def parse_arguments() -> argparse.Namespace:
    """Implementation remains unchanged."""
    parser = argparse.ArgumentParser(description="Parse git history for conference-related commits")
    parser.add_argument("--days", type=int, default=15, help="Number of days to look back in history")
    parser.add_argument("--repo", default=".", help="Path to the git repository (default: current directory)")
    return parser.parse_args()


def main():
    """
    Main execution function with markdown report generation.

    Notes
    -----
    Generates and displays a markdown-formatted report of commits
    """
    args = parse_arguments()
    parser = GitCommitParser(repo_path=args.repo, days=args.days)

    try:
        markdown_report = parser.generate_markdown_report()
        print(markdown_report)

    except subprocess.CalledProcessError:
        print("Error: Failed to analyze git repository. Please ensure you're in a valid git repository.")


if __name__ == "__main__":
    main()
