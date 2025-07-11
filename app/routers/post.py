from .. import models, schemas, oath2
from fastapi import FastAPI, Response, status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from typing import List, Optional


router = APIRouter(
    prefix="/posts",
    tags=["Posts"]
)

# In this example we require authorization for all post operations.
# If you want to allow unauthenticated access to some endpoints, you can remove the Depends
# from oath2.get_current_user() dependency from those endpoints.

# GET all posts
@router.get("/", response_model=List[schemas.PostVoteResponse])
def get_posts(db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user), limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    #posts = db.query(models.Post).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all()

    # Join Post and Vote tables to get the count of likes for each post
    # Using isouter=True to include posts with no votes (likes)
    posts_and_votes= (db.query(models.Post, func.count(models.Vote.post_id).label("likes")).join(models.Vote, models.Post.id == models.Vote.post_id, isouter=True).group_by(models.Post.id).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all())  # type: ignore
    
    # Return a list of dictionaries with post and likes count because response_model expects a list of PostVoteResponse
    return [ {"post": post, "likes": likes} for post, likes in posts_and_votes]  # type: ignore

# GET posts created by the current user
@router.get("/my_posts", response_model=List[schemas.PostVoteResponse])
def get_my_posts(db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user), limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    posts_and_votes_raw= (db.query(models.Post, func.count(models.Vote.post_id).label("likes")).join(models.Vote, models.Post.id == models.Vote.post_id, isouter=True).group_by(models.Post.id).filter(models.Post.owner_id == current_user.id).filter(models.Post.title.contains(search)).limit(limit).offset(skip).all())  # type: ignore
    
    posts= [{"post": post, "likes": likes} for post, likes in posts_and_votes_raw]
    if not posts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have no posts")
    return posts


# GET ID specific post
@router.get("/{id}",response_model=schemas.PostVoteResponse)
def get_post(id: int, db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user)):
    posts_and_votes_raw= (db.query(models.Post, func.count(models.Vote.post_id).label("likes")).join(models.Vote, models.Post.id == models.Vote.post_id, isouter=True).group_by(models.Post.id).filter(models.Post.id == id).first()) # type: ignore
    
    post= [{"post": post, "likes": likes} for post, likes in posts_and_votes_raw] # type: ignore
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The post with the id: {id} was not found")
    return post

# POST a new post
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.PostResponse)
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user)):
    new_post = models.Post(**post.model_dump())
    
    # Set the owner_id to the current user's id
    new_post.owner_id = current_user.id # type: ignore

    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

# DELETE Post
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int, db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user)):
    post = db.query(models.Post).filter(models.Post.id == id).first()
    
    # Check if the post exists
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The post with the id: {id} was not found")
    
    # Check if the current user is the owner of the post
    if post.owner_id != current_user.id:  # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to delete this post")
    
    # Delete the post
    db.delete(post)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Update with PUT
@router.put("/{id}",response_model=schemas.PostResponse)
def update_post(id: int, post: schemas.PostCreate, db: Session = Depends(get_db), current_user: int = Depends(oath2.get_current_user)):
    updated_post = db.query(models.Post).filter(models.Post.id == id)

    # Check if the post exists
    if not updated_post.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"The post with the id: {id} was not found")
    
    # Check if the current user is the owner of the post
    if updated_post.first().owner_id != current_user.id:  # type: ignore
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update this post")
    
    updated_post.update(post.model_dump(), synchronize_session=False) # type: ignore
    db.commit()
    return updated_post.first()