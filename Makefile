layouts/partials:
	mkdir -p $@

layouts/partials/%.html: %.bib | layouts/partials
	bibtex2html -o $(subst .html,,$@) -use-keys -dl -linebreak \
        -noabstract -nokeywords -nobibsource -nofooter -nodoc \
        --named-field url_video video --named-field url_tex tex \
        --named-field url_slides slides --named-field url_press press \
        --named-field url_poster poster --named-field url_manuscript pdf \
        --named-field url_changelog changelog \
        --named-field url_blog_post blog --named-field \
        url_artefact artefact $<
	sed -r -e 's:\[(.*)\]:<b>\1</b>:g' $@ >$@.new && mv $@.new $@
