(function () {
  "use strict";

  function getText(parent, selector) {
    var node = parent.querySelector(selector);
    return node ? node.textContent : "";
  }

  function ensureEmbedScript(accountUrl) {
    var domain = accountUrl.split("/@")[0];
    if (!domain) {
      return;
    }

    var selector = 'script[data-mastodon-embed-base="' + domain + '"]';
    if (document.querySelector(selector)) {
      return;
    }

    var embedScript = document.createElement("script");
    embedScript.src = domain + "/embed.js";
    embedScript.setAttribute("data-mastodon-embed-base", domain);
    document.body.appendChild(embedScript);
  }

  function createFeedItem(link) {
    var post = link.replace(/\/$/, "") + "/embed";
    var feedItem = document.createElement("div");
    var iframe = document.createElement("iframe");

    feedItem.className = "timeline-item";

    iframe.className = "mastodon-embed";
    iframe.src = post;
    iframe.style.width = "100%";
    iframe.style.border = "0";
    iframe.setAttribute("allowfullscreen", "allowfullscreen");
    iframe.loading = "lazy";
    feedItem.appendChild(iframe);
    return feedItem;
  }

  function renderFeed(feedContainer) {
    var account = feedContainer.getAttribute("data-mastodon-account");
    var postLimit = parseInt(feedContainer.getAttribute("data-mastodon-post-limit") || "2", 10);

    if (!account) {
      return;
    }
    if (isNaN(postLimit) || postLimit < 1) {
      postLimit = 2;
    }

    fetch(account + ".rss")
      .then(function (response) {
        return response.text();
      })
      .then(function (xmlText) {
        var xml = new DOMParser().parseFromString(xmlText, "text/xml");
        var items = xml.querySelectorAll("item");
        var rendered = 0;

        feedContainer.textContent = "";

        for (var i = 0; i < items.length && rendered < postLimit; i++) {
          var link = getText(items[i], "link");
          if (!link) {
            continue;
          }

          feedContainer.appendChild(createFeedItem(link));
          rendered += 1;
        }

        ensureEmbedScript(account);
      })
      .catch(function (error) {
        console.log("Error fetching Mastodon RSS feed:", error);
      });
  }

  var feedContainers = document.querySelectorAll("[data-mastodon-account]");
  for (var i = 0; i < feedContainers.length; i++) {
    renderFeed(feedContainers[i]);
  }
})();
