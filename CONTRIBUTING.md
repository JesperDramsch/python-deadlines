# Contributing to Python Deadlines

[![pages-build-deployment](https://github.com/JesperDramsch/python-deadlines/actions/workflows/pages/pages-build-deployment/badge.svg?branch=gh-pages)](https://github.com/JesperDramsch/python-deadlines/actions/workflows/pages/pages-build-deployment) ![GitHub commit activity](https://img.shields.io/github/commit-activity/m/jesperdramsch/python-deadlines) ![GitHub Repo stars](https://img.shields.io/github/stars/jesperdramsch/python-deadlines) [![All Contributors](https://img.shields.io/github/all-contributors/jesperdramsch/python-deadlines?color=ee8449)](#contributors)

Thank you for your interest in contributing to Python Deadlines! This guide will help you get started with making contributions to the project.

## Table of Contents

- [Contributing to Python Deadlines](#contributing-to-python-deadlines)
  - [Table of Contents](#table-of-contents)
  - [Ways to Contribute](#ways-to-contribute)
  - [Adding or Updating Conference Information](#adding-or-updating-conference-information)
    - [Optional Fields](#optional-fields)
  - [Development Setup](#development-setup)
  - [Making Changes](#making-changes)
  - [Pull Request Guidelines](#pull-request-guidelines)
  - [Using All-Contributors Bot](#using-all-contributors-bot)
    - [Contributors](#contributors)
  - [Code Quality](#code-quality)
  - [Getting Help](#getting-help)
  - [Code of Conduct](#code-of-conduct)
  - [License](#license)

## Ways to Contribute

You can contribute in several ways:

-   Adding or updating conference information
-   Improving documentation
-   Fixing bugs
-   Adding new features
-   Reviewing pull requests

## Adding or Updating Conference Information

1. Fork the repository
2. Edit `_data/conferences.yml`
3. Follow this format for conference entries:

```yaml
- conference: BestConf # Title of conference
  year: 2024 # Year
  link: https://example.com # Conference website URL
  cfp: '2024-06-01 23:59:59' # Submission deadline
  place: Berlin, Germany # Location
  start: 2024-09-15 # Conference start date
  end: 2024-09-18 # Conference end date
  sub: PY # Conference type (see below)
```

Required fields:

-   `conference`: Conference name
-   `year`: Conference year
-   `link`: Conference website URL
-   `cfp`: Call for Proposals deadline
-   `place`: Location
-   `start`: Conference start date
-   `end`: Conference end date
-   `sub`: Conference type

Conference types (`sub`):

-   `PY`: General Python
-   `SCIPY`: Scientific Python
-   `DATA`: Python for Data
-   `WEB`: Python for Web
-   `BIZ`: Python for Business
-   `GEO`: Python for Earth

### Optional Fields

You can enhance your entry with these optional fields:

-   `alt_name`: Alternative conference name
-   `cfp_link`: Specific CFP page URL
-   `cfp_ext`: Extended deadline
-   `workshop_deadline`: Workshop submission deadline
-   `tutorial_deadline`: Tutorial submission deadline
-   `timezone`: IANA timezone (defaults to AoE if omitted)
-   `sponsor`: Sponsorship page URL
-   `finaid`: Financial aid information URL
-   `twitter`: Conference Twitter handle
-   `mastodon`: Conference Mastodon URL
-   `note`: Additional important information
-   `location`: Venue coordinates for the map

## Development Setup

1. Install Jekyll (requires Ruby):

```bash
gem install bundler jekyll
```

2. Clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/python-deadlines.git
cd python-deadlines
```

3. Install dependencies:

```bash
bundle install
```

4. Start the local server:

```bash
bundle exec jekyll serve
```

## Making Changes

1. Create a new branch:

```bash
git checkout -b add-conference-name
```

2. Make your changes
3. Test locally
4. Commit with a descriptive message:

```bash
git commit -m "Add ConferenceName 2024"
```

5. Push to your fork:

```bash
git push origin add-conference-name
```

6. Create a Pull Request

## Pull Request Guidelines

-   Use a clear, descriptive title
-   Reference any related issues
-   Include screenshots for UI changes
-   Update documentation if needed
-   Verify all tests pass

## Using All-Contributors Bot

We use the All-Contributors bot to recognize all contributors, not just code contributors. Here's how to use it:

1. Comment on an issue or PR with:

```
@all-contributors please add @username for doc,code,content
```

Available contribution types:

-   `code`: Code or tests
-   `doc`: Documentation
-   `content`: Conference data
-   `review`: Pull Request reviews
-   `bug`: Bug reports
-   `ideas`: Ideas and feedback
-   `tool`: Tools and utilities

2. The bot will create a PR to add the contributor
3. Once merged, they'll appear in the README 🎉

Example:

```
@all-contributors please add @janedoe for content,doc
```

### Contributors

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="http://dramsch.net"><img src="https://avatars.githubusercontent.com/u/2620316?v=4?s=100" width="100px;" alt="Jesper Dramsch"/><br /><sub><b>Jesper Dramsch</b></sub></a><br /><a href="#a11y-JesperDramsch" title="Accessibility">️️️️♿️</a> <a href="https://github.com/JesperDramsch/python-deadlines/issues?q=author%3AJesperDramsch" title="Bug reports">🐛</a> <a href="#blog-JesperDramsch" title="Blogposts">📝</a> <a href="https://github.com/JesperDramsch/python-deadlines/commits?author=JesperDramsch" title="Code">💻</a> <a href="#conference-JesperDramsch" title="Python conference (Added or updated)">📆</a> <a href="#content-JesperDramsch" title="Content">🖋</a> <a href="https://github.com/JesperDramsch/python-deadlines/commits?author=JesperDramsch" title="Documentation">📖</a> <a href="#design-JesperDramsch" title="Design">🎨</a> <a href="#financial-JesperDramsch" title="Financial">💵</a> <a href="#ideas-JesperDramsch" title="Ideas, Planning, & Feedback">🤔</a> <a href="#infra-JesperDramsch" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a> <a href="#promotion-JesperDramsch" title="Promotion">📣</a> <a href="https://github.com/JesperDramsch/python-deadlines/pulls?q=is%3Apr+reviewed-by%3AJesperDramsch" title="Reviewed Pull Requests">👀</a> <a href="#security-JesperDramsch" title="Security">🛡️</a> <a href="#tool-JesperDramsch" title="Tools">🔧</a> <a href="#translation-JesperDramsch" title="Translation">🌍</a> <a href="#talk-JesperDramsch" title="Talks">📢</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://abhishekdas.com/"><img src="https://avatars.githubusercontent.com/u/1156489?v=4?s=100" width="100px;" alt="Abhishek Das"/><br /><sub><b>Abhishek Das</b></sub></a><br /><a href="https://github.com/JesperDramsch/python-deadlines/commits?author=abhshkdz" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://coefficient.ai"><img src="https://avatars.githubusercontent.com/u/2884159?v=4?s=100" width="100px;" alt="John Sandall"/><br /><sub><b>John Sandall</b></sub></a><br /><a href="#conference-john-sandall" title="Python conference (Added or updated)">📆</a> <a href="https://github.com/JesperDramsch/python-deadlines/issues?q=author%3Ajohn-sandall" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://thib.me/"><img src="https://avatars.githubusercontent.com/u/877585?v=4?s=100" width="100px;" alt="Thibaud Colas"/><br /><sub><b>Thibaud Colas</b></sub></a><br /><a href="#conference-thibaudcolas" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://tanka.la"><img src="https://avatars.githubusercontent.com/u/29096822?v=4?s=100" width="100px;" alt="Tankala Ashok"/><br /><sub><b>Tankala Ashok</b></sub></a><br /><a href="#conference-tankala" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://robdewit.nl"><img src="https://avatars.githubusercontent.com/u/7165065?v=4?s=100" width="100px;" alt="Rob de Wit"/><br /><sub><b>Rob de Wit</b></sub></a><br /><a href="#conference-RCdeWit" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://slides.takanory.net/"><img src="https://avatars.githubusercontent.com/u/988241?v=4?s=100" width="100px;" alt="Takanori Suzuki"/><br /><sub><b>Takanori Suzuki</b></sub></a><br /><a href="#conference-takanory" title="Python conference (Added or updated)">📆</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/alanderex"><img src="https://avatars.githubusercontent.com/u/1356401?v=4?s=100" width="100px;" alt="Alexander CS Hendorf"/><br /><sub><b>Alexander CS Hendorf</b></sub></a><br /><a href="#conference-alanderex" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/radujica"><img src="https://avatars.githubusercontent.com/u/8166962?v=4?s=100" width="100px;" alt="Radu"/><br /><sub><b>Radu</b></sub></a><br /><a href="https://github.com/JesperDramsch/python-deadlines/issues?q=author%3Aradujica" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://isabelizimm.me"><img src="https://avatars.githubusercontent.com/u/54685329?v=4?s=100" width="100px;" alt="Isabel Zimmerman"/><br /><sub><b>Isabel Zimmerman</b></sub></a><br /><a href="https://github.com/JesperDramsch/python-deadlines/issues?q=author%3Aisabelizimm" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://jeroenjanssens.com/"><img src="https://avatars.githubusercontent.com/u/1368256?v=4?s=100" width="100px;" alt="Jeroen Janssens"/><br /><sub><b>Jeroen Janssens</b></sub></a><br /><a href="#conference-jeroenjanssens" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/systematicguy"><img src="https://avatars.githubusercontent.com/u/12820811?v=4?s=100" width="100px;" alt="David Horvath"/><br /><sub><b>David Horvath</b></sub></a><br /><a href="#conference-systematicguy" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://ogrisel.com/"><img src="https://avatars.githubusercontent.com/u/89061?v=4?s=100" width="100px;" alt="Olivier Grisel"/><br /><sub><b>Olivier Grisel</b></sub></a><br /><a href="#conference-ogrisel" title="Python conference (Added or updated)">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/mtsokol"><img src="https://avatars.githubusercontent.com/u/8431159?v=4?s=100" width="100px;" alt="Mateusz Sokół"/><br /><sub><b>Mateusz Sokół</b></sub></a><br /><a href="#conference-mtsokol" title="Python conference (Added or updated)">📆</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/theopinard"><img src="https://avatars.githubusercontent.com/u/16977967?v=4?s=100" width="100px;" alt="Theodore Meynard"/><br /><sub><b>Theodore Meynard</b></sub></a><br /><a href="#conference-theopinard" title="Python conference (Added or updated)">📆</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## Code Quality

-   Follow PEP 8 for Python code
-   Use meaningful variable names
-   Add comments for complex logic
-   Include docstrings for functions
-   Validate YAML files before committing

## Getting Help

-   Open an issue for questions
-   Join discussions in existing issues
-   Contact maintainers for guidance

## Code of Conduct

Please follow our Code of Conduct in all project interactions. Report violations to the project maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
