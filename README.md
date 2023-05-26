## Python Deadlines [![pages-build-deployment](https://github.com/JesperDramsch/python-deadlines/actions/workflows/pages/pages-build-deployment/badge.svg?branch=gh-pages)](https://github.com/JesperDramsch/python-deadlines/actions/workflows/pages/pages-build-deployment)

Countdown timers to keep track of a bunch of Python conference deadlines.

## Contributing

Contributions are very welcome!

![GIF of adding a conference to pythondeadlin.es](static/img/pythondeadlines-edit.gif)

To add or update a deadline:
- Fork the repository
- Update `_data/conferences.yml`
- Make sure it has the `title`, `year`, `id`, `link`, `cfp`, `timezone`, `date`, `place`, `sub` attributes
    + This [online web app](https://timezonefinder.michelfe.it/) makes it easy to find timezones – just click! 
      (Based on [timezonefinder](https://github.com/jannikmi/timezonefinder) library)
    + Alternatively, see available timezone strings [here](https://momentjs.com/timezone/).
- Optionally add a `note`
- Send a [pull request](_data/conferences.yml)

If that is not possible you can try and submit your conference through this [Google Form](https://forms.gle/UUqiprHjRfvGp6Fs6) but that may take a second.

### Example

```yaml
- title: BestConf                          # Title of conference without year
  year: 2022                               # Year
  link: link-to-website.com                # URL to conference
  cfp_link: link-to-cfp.com                 # URL to call for proposals (Optional)
  cfp: 'YYYY-MM-DD HH:mm:ss'               # Deadline for Call for Participation / Proposals
  workshop_deadline: 'YYYY-MM-DD HH:mm:ss' # Workshop deadline if different from cfp (Optional)
  tutorial_deadline: 'YYYY-MM-DD HH:mm:ss' # Tutorial deadline if different from cfp (Optional)
  timezone: Asia/Seoul                     # Standard IANA Timezones (Omit for AoE)
  place: Incheon, South Korea              # City, Country
  date: September 18 - 22, 2022            # Nicely written dates of conference
  start: YYYY-MM-DD                        # Start date of conference for calendar
  end: YYYY-MM-DD                          # End date of conference for calendar
  sponsor: link-to-sponsor.page            # URL to Sponsorship page (Optional)
  finaid: link-to-finaid.page              # URL to Financial Aid page (Optional)
  twitter: BestConfEver                    # Twitter handle of conference (Optional)
  mastodon: https://mastodon.social/@bconf # Mastodon handle of conference (Optional)
  sub: PY                                  # Type of conference (see or add _data/types.yml)
  note: Important                          # In case there are extra notes about the conference (Optional)
  location:                                # Geolocation for inclusion in map
    latitude: 0.00
    longitude: 0.00
```

### Description of entries

| `sub`       | Description                                        | Type    | Required |
| ----------- | ------------------------------------------------- | ------- | -------- |
| `title`     | Title of the conference                           | `str`   | ✔       |
| `year`      | Year of this conference                           | `int`   | ✔       |
| `link`      | URL to conference                                 | `str`   | ✔       |
| `cfp_link`   | URL to call for proposals                         | `str`   |          |
| `cfp`       | Deadline for Call for Participation / Proposals   | `str`   | ✔       |
| `workshop_deadline` | Workshop deadline if different from cfp   | `str`   |          |
| `tutorial_deadline` | Tutorial deadline if different from cfp   | `str`   |          |
| `timezone`  | Standard [IANA Timezones](https://timezonefinder.michelfe.it/) (Omit for AoE)            | `str`   | ✔       |
| `place`     | City, Country                                     | `str`   | ✔       |
| `date`      | Nicely written dates of conference                | `str`   | ✔       |
| `start`     | Start date of conference for calendar             | `date`  | ✔       |
| `end`       | End date of conference for calendar               | `date`  | ✔       |
| `finaid`    | URL to financial aid information                  | `str`   |          |
| `sponsor`   | URL to sponsorship opportunities                  | `str`   |          |
| `twitter`   | Twitter handle of conference                      | `str`   |          |
| `mastodon`  | Mastodon handle of conference                     | `str`   |          |
| `sub`       | Type of conference                                | `str`   |          |
| `note`      | Extra notes about the conference                  | `str`   |          |
| `location`  | Geolocation for inclusion in map                  | `str`   |          |
| `latitude`  | Latitude of venue                                 | `float` |          |
| `longitude` | Longitude of venue                                | `float` |          |


### Conference types for `sub`

| `sub`    | Category name     |
| -------- | ----------------- |
| `PY`     | General Python    |
| `SCIPY`  | Scientific Python |                                              |
| `PYDATA` | Python for Data   |
| `WEB`    | Python for Web    |


## Forks & other useful listings

- [aideadlines][2] the original
- [geodeadlin.es][3] by @LukasMosser
- [neuro-deadlines][4] by @tbryn
- [ai-challenge-deadlines][5] by @dieg0as
- [CV-oriented ai-deadlines (with an emphasis on medical images)][8] by @duducheng
- [es-deadlines (Embedded Systems, Computer Architecture, and Cyber-physical Systems)][9] by @AlexVonB and @k0nze
- [2019-2020 International Conferences in AI, CV, DM, NLP and Robotics][10] by @JackieTseng
- [ccf-deadlines][11] by @ccfddl
- [netdeadlines.com][12] by @albertgranalcoz
- [ad-deadlines.com][13] by @daniel-bogdoll

## License

This project is licensed under [MIT][1].

It uses:

- [IcoMoon Icons](https://icomoon.io/#icons-icomoon): [GPL](http://www.gnu.org/licenses/gpl.html) / [CC BY4.0](http://creativecommons.org/licenses/by/4.0/)

[1]: https://abhshkdz.mit-license.org/
[2]: http://aideadlin.es/
[3]: https://github.com/LukasMosser/geo-deadlines
[4]: https://github.com/tbryn/neuro-deadlines
[5]: https://github.com/dieg0as/ai-challenge-deadlines
[6]: http://www.conferenceranks.com/#
[8]: https://m3dv.github.io/ai-deadlines/
[9]: https://ekut-es.github.io/es-deadlines/
[10]: https://jackietseng.github.io/conference_call_for_paper/conferences.html
[11]: https://ccfddl.github.io/
[12]: https://netdeadlines.com/
[13]: https://ad-deadlines.com/
