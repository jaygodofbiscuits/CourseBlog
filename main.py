from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from requests import Response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from flask_login import (
    UserMixin,
    login_user,
    LoginManager,
    login_required,
    current_user,
    logout_user,
)
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

##SET UP APP
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///blog.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

Base = declarative_base()  ##needed for relational db

##SET GRAVATARS - the little icons used in the lecture
gravatar = Gravatar(
    app,
    size=100,
    rating="g",
    default="retro",
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None,
)


##SET UP LOG IN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

##USER LOADER CALLBACK
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


##CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship(
        "User", back_populates="posts"
    )  ## back_populates references posts in User and vice versa
    comments = relationship("Comment", back_populates="b_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    posts = relationship(
        "BlogPost", back_populates="author"
    )  ## back_populates references author in BlogPost and vice versa
    comments = relationship("Comment", back_populates="author")


class Comment(UserMixin, db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")
    b_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    b_post = relationship("BlogPost", back_populates="comments")


db.create_all()

##CREATE THE ADMIN ONLY WRAPPER FUNCTION
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:  # no log in at all
            abort(403)
        elif current_user.id != 1:  # not the admin
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


##ROUTES


@app.route("/")
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        ##CHECK FOR EMAIL IN DB
        a_user = User.query.filter_by(email=form.email.data).first()
        if a_user:
            flash("That email address is  already in use. Try logging in.")
            return redirect(url_for("login"))
        new_user = User(
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            name=form.name.data,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect("/")
    return render_template("register.html", form=form, current_user=current_user)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()

        if user == None:
            flash("This email hasn't been registered.")
            return render_template("register.html", form=form)

        if check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(
                url_for("get_all_posts", logged_in=current_user.is_authenticated)
            )
        else:
            flash("Incorrect password.")
            return render_template("login.html", form=form)
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("get_all_posts"))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Log in to post comments.")
            return redirect(url_for("login"))
        else:
            new_comment = Comment(
                text=comment_form.body.data,
                author=current_user,
                b_post=requested_post,
            )
            db.session.add(new_comment)
            db.session.commit()
            comment_form.body.data = ""
            return render_template(
                "post.html",
                post=requested_post,
                comment_form=comment_form,
                current_user=current_user,
            )
    return render_template(
        "post.html",
        post=requested_post,
        comment_form=comment_form,
        current_user=current_user,
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


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
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
