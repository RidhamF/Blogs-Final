import functools
import os
from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm,Register,Login,Comment_Form



app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_API_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_URI')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author = relationship("User",back_populates='blogs')
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    comments = relationship("Comment", back_populates="blog")


# TODO: Create a User table for all your registered users. 
class User(db.Model,UserMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    blogs = relationship("BlogPost",back_populates="author")
    comments = relationship("Comment",back_populates="author")

    def get(self,user_id):
        return db.session.execute(db.select(User).where(User.id==user_id)).scalar()

class Comment(db.Model,UserMixin):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    body = mapped_column(Text)
    blog = relationship("BlogPost", back_populates="comments")
    author = relationship("User",back_populates="comments")
    author_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))
    blog_id: Mapped[int] = mapped_column(db.ForeignKey("blog_posts.id"))


with app.app_context():
    db.create_all()

def admin_only(func):
    @functools.wraps(func)
    def wrapper(*args,**kwargs):
        if current_user.id==1:
            return func(*args,**kwargs)
        else:
            return abort(403)
    return wrapper

@login_manager.user_loader
def load_user(user_id):
    return User().get(user_id)

logged_in = False

# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=['GET','POST'])
def register():
    global logged_in
    form = Register()
    if form.validate_on_submit():
        emails = [user.email for user in db.session.execute(db.select(User)).scalars().all()]
        if form.email.data in emails:
            flash("Email already in use. Login instead")
            logged_in = False
            return redirect(url_for('login'))
        else:
            hash = generate_password_hash(form.password.data,"pbkdf2:sha256",8)
            user = User(email=form.email.data,password=hash,name=form.name.data)
            db.session.add(user)
            login_user(user)
            logged_in = True
            db.session.expunge(user)
            db.session.commit()
            return redirect(url_for('get_all_posts'))
    return render_template("register.html",form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods=['GET','POST'])
def login():
    global logged_in
    form  = Login()
    if form.validate_on_submit():
        email = form.email.data
        emails = [user.email for user in db.session.execute(db.select(User)).scalars().all()]
        if email in emails:
            password = db.session.execute(db.select(User).where(User.email==email)).scalar().password
            if check_password_hash(password,form.password.data):
                user = db.session.execute(db.select(User).where(User.email==email)).scalar()
                logged_in = True
                login_user(user)
                db.session.expunge(user)
                db.session.commit()
                return redirect(url_for("get_all_posts"))
            else:
                flash("Wrong Password")
                logged_in = False
                return redirect(url_for("login"))
        else:
            flash("No such user")
            logged_in = False
            return redirect(url_for("login"))

    return render_template("login.html",form=form)


@app.route('/logout')
def logout():
    global logged_in
    logout_user()
    logged_in=False
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts,logged_in=logged_in,current_user = current_user)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=["GET",'POST'])
def show_post(post_id):
    form = Comment_Form()
    requested_post = db.get_or_404(BlogPost, post_id)
    if form.validate_on_submit():
        if logged_in:
            comment = Comment(body=form.body.data,author=current_user,blog=requested_post)
            db.session.add(comment)
            db.session.commit()
        else:
            flash("Please log in to comment on a blog.")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post,current_user=current_user,form=form,logged_in=logged_in)


# TODO: Use a decorator so only an admin user can create a new post
@login_required
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@login_required
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@login_required
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False, port=5002)
