# Catalog
Application name: Catalog
Created by Jerry Maurice

-Description
This application is written in Python, more precisely python 2.7. It displays a list of catalog related to sports. In each sport category there is a list of items related to this category. For example there is category called snowboarding and in this category we can find snowboard and goggles.
This application can be viewed by a member and a non-member. The difference between the two is that a member is a registered user that has the ability to create change to the catalog. When a non-member run the application, the first view he or she will see is the list of catalog. Next to each catalog, this user has the possibility to view the items corresponding to that category which bring to the second view. Each item is provided a description which this user can see by clicking on the little icon next to the item. On every page visited if the user want to go to the homepage which is the page which is the view with the list of catalog, the user will just have to click on the title of the application which is located on the navigation bar. This is as far as possible a non member can go. What great about this application is that any non member can become a registered user. The view of the registered user is different from a non registered one. In other to login or register to the application, the user will have to click on login. Once the user click this button, he will be redirected to a page where he will be able to select his google account to log in. Once the user log in he will redirected again to the categories view. This view is different from the view of the non member. In addition to the view function, this view show additional function where the user is also able to edit, add, and delete. The same applies to when this user click on the view icon to be redirected to the items view. When the user is finish he will just have to click on logout button located in the navigation bar.

-features
This application has some interesting features
It implement a third party authentication and authorization service
It provides a JSON endpoint api that serves the same information as displayed in the HTML endpoints
It limits the request of the endpoint to 30 per each minute
It uses SQLAlchemy and the flask framework

-How to run the application
Before this application was created, vagrant and virtualbox were installed. First, this link is provided to download virtual box - www.virtualbox.org and this www.vagrantup.com is to download vagrant. Once installed to quickly start just clone this repository found at https://github.com/udacity/fullstack-nanodegree-vm. Because everything is already installed, no need to install other packages. We only need to copy the files I provided into the repository you cloned to your computer. There would be a duplicate problem but before you copied the submitted folder delete the one that was there before "catalog". 
It's time to run the project.
First vagrant need to be running:
Step to do it
	1. Vagrant up
	2. Vagrant ssh
Once running
	1. cd /vagrant
	2. cd catalog
Running the Application:
	Since the program is written in Python 2.7, in order to run the program just type python application.py. The program listen to the port 5000. On your favorite browser type localhost:5000 and you will be able to see the application.

Api Endpoint
The api provided give a registered user the ability to get, post, put, delete a category and item in the category
Route to access them:
1. Categories - GET, POST:
	localhost:5000/catalog/categories
2. Category - GET, PUT, DELETE:
	localhost:5000/catalog/categories/<int:id>
3. Items in the category - GET, POST:
	localhost:5000/catalog/category/items/<int:id>
4. Specific item in the category - GET, PUT, DELETE:
	localhost:5000/catalog/category/<int:id>/items/<int:item_id>
