# frozen_string_literal: true
require 'fileutils'
require 'json'
require 'execjs'
require 'nokogiri'
require 'kramdown'

module Jekyll

  class SearchIndexFile < Jekyll::StaticFile
    # Override write as the index.json index file has already been created
    def write(dest)
    true
    end
  end

  class LunrSearchIndexGenerator < Jekyll::Generator
    safe true
    priority :low

    # Initialize with site configuration
    def initialize(config = {})
      super(config)

      # Get lunr config from _config.yml or use defaults
      @config = config['lunr_search'] || {}
      @config['index_dir'] ||= 'assets/search'  # Directory for the index file
      @config['index_name'] ||= 'search_index'  # Name of the generated index file

      # Fields to index with their boost values
      @config['fields'] ||= {
        'title' => 10,
        'content' => 1,
        'url' => 1,
        'date' => 1,
        'place' => 1,
        'alt_name' => 10,
        'subs' => 1,
        'link' => 1
      }
    end

    def generate(site)
      Jekyll.logger.info 'Lunr:', 'Generating search index...'

      # Get the documents to index
      items = get_documents_to_index(site)

      # Create the index
      index = build_index(site, items)

      # Write the index file
      write_index_file(site, index, items)

      Jekyll.logger.info 'Lunr:', 'Search index generated successfully'
    end

    private

    def get_documents_to_index(site)
      items = []

      # Add posts
      site.posts.docs.each do |post|
        items << {
          'id' => post.url.to_s,
          'title' => post.data['title'].to_s,
          'content' => extract_content(post.content),
          'url' => post.url,
          'date' => post.date.strftime('%Y-%m-%d'),
          'place' => '',
          'subs' => '',
          'link' => '',
          'alt_name' => ''
        }
      end

      # Add conference data
      if site.data['conferences']
        confs = []
        confs.concat(site.data['archive']) if site.data['archive']
        confs.concat(site.data['conferences']) if site.data['conferences']
        confs.concat(site.data['legacy']) if site.data['legacy']

        confs.each do |conf|
          next unless conf && conf['conference']
          items << {
            'id' => "#{conf['conference'].to_s.downcase.gsub(/\s+/, '-')}-#{conf['year']}",
            'title' => "#{conf['conference']} #{conf['year']}",
            'content' => "#{conf['conference']} #{conf['year']}",
            'url' => "#{site.baseurl}/conference/#{conf['conference'].to_s.downcase.gsub(/\s+/, '-')}-#{conf['year']}",
            'date' => format_conference_date(conf['start'], conf['end']),
            'place' => conf['place'].to_s,
            'subs' => conf['sub'].to_s,
            'link' => conf['link'].to_s,
            'alt_name' => conf['alt_name'].to_s
          }
        end
      end

      items
    end

    def build_index(site, items)
      # Load lunr.js
      lunr_path = File.join(site.source, "/static/js/lunr.min.js")
      lunr_js = File.read(lunr_path)
      ctx = ExecJS.compile(lunr_js)

      # Prepare the documents for lunr
      documents = items.map do |item|
        doc = {}
        @config['fields'].each_key do |field|
          doc[field] = item[field].to_s if item[field]
        end
        doc['id'] = item['id']
        doc
      end

      # Create the lunr index configuration and add documents
      index_js = <<-JS
        lunr(function() {
          this.ref('id');
          #{@config['fields'].map { |field, boost| "this.field('#{field}', {boost: #{boost}});" }.join("\n")}

          var docs = #{documents.to_json};
          docs.forEach(function(doc) {
            this.add(doc);
          }, this);
        })
      JS

      # Build and return the index
      ctx.eval(index_js)
    end

    def write_index_file(site, index, items)
      # Prepare the index directory
      index_dir = File.join(site.dest, @config['index_dir'])
      FileUtils.mkdir_p(index_dir)

      # Create the combined index and documents file
      data = {
        'index' => index,
        'docs' => items.map { |item| [item['id'], item] }.to_h
      }

      # Write to file
      index_file = File.join(index_dir, "#{@config['index_name']}.json")
      File.write(index_file, JSON.generate(data))

      # Register the file with Jekyll
      site.static_files << Jekyll::SearchIndexFile.new(
        site,
        site.dest,
        @config['index_dir'],
        "#{@config['index_name']}.json"
      )
    end

    def extract_content(content)
      return '' unless content
      # Convert markdown to HTML and strip all tags
      html = Kramdown::Document.new(content).to_html
      Nokogiri::HTML(html).text.strip.gsub(/\s+/, ' ')
    end

    def format_conference_date(start_date, end_date)
      return '' unless start_date && end_date
      "#{start_date} - #{end_date}"
    end
  end
end
