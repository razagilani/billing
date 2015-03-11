These scripts are executed via the CLI and require the authentication and database information to be passed into the CLI tools that run these files.

For Mongo:

 mongo [host]/[db]_[env] file.js


For MySQL:

 mysql -u[user]-[env] -p[passwd] -D[db]_[env] < file.sql 
