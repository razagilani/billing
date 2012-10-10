ReeBill web application directory

art - original artwork directory, not deployed, exports of these files usually go into www/images
doc - specific to the application
test - test harnesses, ui test, example programs, unit tests, etc.  still needs to evolve

www/ - all web serveable/cacheable files
www/images - image directory
www/js - javacript directory
www/js/[framework] - third party JS framework dirs

src - all WSGI related files - things callable from the web, but not intended to be served via the webb
configuration files - configurations used to configure objects found here and in ../processing

stuff to move around:
ui/* moves to www
WSGI code and other code remains in ./reebill
bill_mailer.py - pull jinja template out and keep it here, make smtp mailer generic and move it to ../processing

Stuff to move to generic processing framework located at ../processing:
journal.py - move it to ../processing
render.py - move it to ../processing
