
      // calendar data template
      var calendar_data = {
        clickDay: function (e) {
          if (e.events.length > 0) {
            for (var i in e.events) {
              window.open("{{site.baseurl}}/conference/" + e.events[i].abbreviation, "_self")
            }
          }
        },
        mouseOnDay: function (e) {
          if (e.events.length > 0) {
            var content = "";

            for (var i in e.events) {
              var headline_color = "";
              var break_html = '<hr>';

              var location_html = '<img src="/static/img/072-location.svg" className="own-badge" alt="Location icon" width="16" height="16"/>&nbsp;' + e.events[i].location;
              var date_html = '<img src="/static/img/084-calendar.svg" className="own-badge" alt="Calendar icon" width="16" height="16"/>&nbsp;' + e.events[i].date;

              var badges_html = "";
              var subs = e.events[i].subject.split(',');
              for (let i = 0; i < subs.length; i++) {
                var sub = subs[i].replace(" ", "");
                badges_html += '<span class="conf-sub conf-badge-small">' + sub + '</span>'
              }

              if (i == e.events.length - 1) {
                break_html = '';
              }


              if (e.events[i].id.endsWith("deadline")) {
                headline_color = 'deadline-text';
              } else {
              }
              content +=
                '<div class="event-tooltip-content position-relative">' +
                '<div class="event-name ' + headline_color + '">' +
                '<b><a href="{{site.baseurl}}/conference/' + e.events[i].abbreviation + '" class="stretched-link">' + e.events[i].name + '</a></b>' +
                '</div>' +
                '<div class="event-location">' +
                location_html +
                '<br>' +
                date_html +
                '<br>' +
                badges_html +
                '</div>' +
                break_html +
                '</div>';
            }

            $(e.element).popover({
              trigger: "manual",
              container: "body",
              html: true,
              content: content,
            });

            $(e.element).popover("show");
            timeoutPopover(e);
          }
        },
        focusoutDay: function (e) {
          // if (e.events.length > 0) {
          //   $(e.element).popover("hide");
          // }
          timeoutPopover(e);
        },
        customDayRenderer: function (cellContent, currentDate) {
          var today = new Date();
          // render today
          if (today.getFullYear() === currentDate.getFullYear() && today.getMonth() === currentDate.getMonth() && today.getDate() === currentDate.getDate()) {
            cellContent.style = "background-color: gray;";
          }
        },
        dayContextMenu: function (e) {
          // $(e.element).popover("hide");
          timeoutPopover(e);
        },
        dataSource: conf_list_all
}

// Function to show the popover
function timeoutPopover(e) {
  // Ensure e has a property to store the timeout if it doesn't already exist
  if (!e.hidePopoverTimeout) {
    e.hidePopoverTimeout = null;
  }

  // Mouse enter event for the calendar item to show the popover
  $(e.element).mouseover(function() {
    clearTimeout(e.hidePopoverTimeout); // Cancel any pending hide operation
    $(e.element).popover('show');
  });

  // Mouse leave event for the calendar item to hide the popover
  $(e.element).mouseout(function() {
    // Start a timeout when leaving the element, gives a buffer time to move to the popover
    e.hidePopoverTimeout = setTimeout(function() {
      $(e.element).popover('hide');
    }, 300); // Adjust delay as needed
  });

    // Prevent popover from hiding when mouse is over the popover
  $("body").on('mouseover', '.popover', function() {
    clearTimeout(e.hidePopoverTimeout);
  }).on('mouseout', '.popover', function() {
    // Hide the popover when leaving it after a delay, allows returning to the calendar item
    e.hidePopoverTimeout = setTimeout(function() {
      $(e.element).popover('hide');
    }, 300); // Adjust delay as needed
  });
}


function load_conference_list() {
  // Gather data
  var conf_list_all = [];
  {% for conf in site.data.conferences + site.data.archive %}
    {% if conf.cfp_ext %}
			{% assign cfp = conf.cfp_ext %}
      {% assign extended = "(extended)" %}
		{% else %}
			{% assign cfp = conf.cfp %}
		{% endif %}
    {% capture conf_date %}{%- translate_file dates/pretty_dates.html start=conf.start end=conf.end -%}{% endcapture %}
    // add deadlines in red
    conf_list_all.push({
      id: "{{conf.conference | slugify: "latin"}}-{{conf.year}}-deadline",
      abbreviation: "{{conf.conference | slugify: "latin"}}-{{conf.year}}",
      name: "{{conf.conference}} {{conf.year}} CfP {{extended}}",
      color: "red",
      location: "{{conf.place}}",
      date: "{{conf_date | strip}}",
      subject: "{{conf.sub}}",
      startDate: Date.parse("{{cfp}}"),
      endDate: Date.parse("{{cfp}}"),
    });
    {% if conf.workshop_deadline %}
    conf_list_all.push({
      id: "{{conf.conference | slugify: "latin"}}-{{conf.year}}-deadline",
      abbreviation: "{{conf.conference | slugify: "latin"}}-{{conf.year}}",
      name: "{{conf.conference}} {{conf.year}} Workshop Deadline",
      color: "red",
      location: "{{conf.place}}",
      date: "{{ conf_date | strip }}",
      subject: "{{conf.sub}}",
      startDate: Date.parse("{{conf.workshop_deadline}}"),
      endDate: Date.parse("{{conf.workshop_deadline}}"),
    });
    {% endif %}
    {% if conf.tutorial_deadline %}
    conf_list_all.push({
      id: "{{conf.conference | slugify: "latin"}}-{{conf.year}}-deadline",
      abbreviation: "{{conf.conference | slugify: "latin"}}-{{conf.year}}",
      name: "{{conf.conference}} {{conf.year}} Tutorial Deadline",
      color: "red",
      location: "{{conf.place}}",
      date: "{{ conf_date | strip }}",
      subject: "{{conf.sub}}",
      startDate: Date.parse("{{cfp}}"),
      endDate: Date.parse("{{cfp}}"),
    });
    {% endif %}

    // add Conferences in chosen color
    {% if conf.start != "" %}
      var color = "black";
      {% assign conf_sub = conf.sub | split: ',' | first | strip %} // use first sub to choose color
      {% for type in site.data.types %}
            {% if conf_sub == type.sub %}
                    color = "{{type.color}}";
            {% endif %}
      {% endfor %}
      conf_list_all.push({
        id: "{{conf.conference | slugify: "latin"}}-{{conf.year}}-conference",
        abbreviation: "{{conf.conference | slugify: "latin"}}-{{conf.year}}",
        name: "{{conf.conference}} {{conf.year}}",
        color: color,
        location: "{{conf.place}}",
        date: "{{ conf_date | strip }}",
        subject: "{{conf.sub}}",
        startDate: Date.parse("{{conf.start}}"),
        endDate: Date.parse("{{conf.end}}"),
      });
    {% endif %}
  {% endfor %}

  return conf_list_all;
}

function update_filtering(data) {
  // Defensive check for data parameter
  if (!data || typeof data !== 'object' || !data.subs || !Array.isArray(data.subs)) {
    console.error('calendar update_filtering called with invalid data:', data);
    return;
  }

  store.set('{{site.domain}}-subs', {subs: data.subs, timestamp: new Date().getTime()});

  conf_list = conf_list_all.filter(v => {
    var commonValues = data.subs.filter(function (value) {
      return v.subject.indexOf(value) > -1;
    });
    var subject_match = commonValues.length > 0;
    return subject_match;
  });

  // rerender calendar
  calendar_data['dataSource'] = conf_list;  // need to update only this
  calendar_data['language'] = "{{site.lang}}";
  calendar = new Calendar("#calendar-page", calendar_data);

  if (data.subs.length === 0 || data.subs.length == data.all_subs.length) {
		window.history.pushState('', '', page_url);
	} else {
		// Join the selected values into a query parameter
		window.history.pushState('', '', page_url + '?sub=' + data.subs.join());
	}
}
