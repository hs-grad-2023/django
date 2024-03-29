import shutil
from sqlite3 import IntegrityError
import sqlite3
import sys
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from .api import get_loc_data, get_time, get_weather_data, get_icon
from .models import clothes, photos, Musinsa, Comment, viton_upload_cloth,viton_upload_model, viton_upload_result
from django.contrib.auth import authenticate, login
from .forms import UserForm, LoginForm, ModifyForm, CommentForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils.crypto import get_random_string
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from allauth.account.signals import user_signed_up, user_logged_in
from django.db.models import Q
from functools import reduce
from operator import or_
from allauth.socialaccount.models import SocialAccount
from django.db.models.expressions import Window
from django.db.models.functions import RowNumber
from django.db.models import F
import json
from ast import literal_eval
from django.core.paginator import Paginator
import io
import base64
from django.core.files import File
from PIL import Image, ImageDraw, ImageFont
from itertools import chain
from django.views.decorators.http import require_POST
import cvzone
import cv2
from cvzone.PoseModule import PoseDetector
import os
import numpy as np
import datetime, time, pygame
from muapp.viton import clothmask
import re, random
import openai
import torch
from segment_anything import sam_model_registry, SamPredictor
import re, random
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from io import BytesIO
openai.api_key ="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"


User = get_user_model()

# def 404(request):
#     return render(request,"404.html")

typeCategory = {
        '상의':  ["== 상의 ==","니트/스웨터","셔츠/블라우스","후드 티셔츠", "피케/카라 티셔츠","맨투맨/스웨트셔츠", "반소매 티셔츠","긴소매 티셔츠","민소매 티셔츠","기타 상의"],
        '하의': ["== 하의 ==","데님 팬츠","숏 팬츠","코튼 팬츠", "레깅스","슈트 팬츠/슬랙스","점프 슈트/오버올","트레이닝/조거 팬츠","기타 바지"],
        '치마': ["== 치마 ==","미니 스커트", "미디 스커트","롱 스커트"],
        '원피스': ["== 원피스 ==","미니 원피스", "미디 원피스","맥시 원피스"],
        '아우터': ["== 아우터 ==","후드 집업","환절기 코트", "블루종/MA-1","겨울 코트", "레더/라이더스 재킷","무스탕/퍼","롱패딩/롱헤비 아우터","슈트/블레이저 재킷","숏패딩/숏헤비 아우터","카디건","아노락 재킷","패딩 베스트","플리스/뽀글이","트레이닝 재킷","기타 아우터"],
        '가방': ["== 가방 ==","백팩","메신저/크로스 백","파우치 백","숄더백","에코백","토트백","클로치 백","웨이스트백/힙색"],
        '악세서리': ["== 악세서리 ==","모자","레그웨어","머플러","장갑","시계","팔찌","귀걸이","반지","발찌","목걸이","헤어 액세서리"],
        '신발': ["== 신발 ==","구두","샌들","로퍼","힐/펌프스","플랫 슈즈","부츠","캔버스/단화","스포츠 스니커즈"],
        '가상피팅' : ["== 가상피팅 ==", "상의", "하의", "코디"],
}

allTypeCategory = [ "== 상의 ==", "== 하의 ==","== 치마 ==","== 원피스 ==","== 아우터 ==","== 가방 ==","== 악세서리 ==","== 신발 ==","== 가상피팅 =="]

@receiver(user_signed_up)
def add_social_user_name(sender, request, user, **kwargs):
    social_accounts = SocialAccount.objects.get(user=user)
    user.first_name = get_random_string(length=16)
    if social_accounts.provider == 'kakao':
        user.name = social_accounts.extra_data['properties']['nickname']
    else:
        user.name = social_accounts.extra_data['name']
    user.save()
    dpath = os.path.join("_media", "imgfiles", "VirtualFitting", "User" , f"{user.first_name}")
    copy = os.path.join("muapp", "VirtualFitting", "Resources", "1.png")

    os.makedirs(os.path.join(dpath, "Shirts"), exist_ok=True)
    os.makedirs(os.path.join(dpath, "Pants"), exist_ok=True)

    shutil.copyfile(copy, os.path.join(dpath, "Shirts", "1.png"))#default사진 복사
    shutil.copyfile(copy, os.path.join(dpath, "Pants", "1.png"))
    messages.success(request, '축하합니다!!\nClothify의 회원가입이 완료되었습니다!')


def index(request):

    clothesobject = clothes.objects.all()   #clothes의 모든 객체를 c에 담기

    try:
        location = get_loc_data()
        date = get_time()
        weather = get_weather_data()
        icon = get_icon()
        results= {
            'location' : location,
            'date' : date,
            'minTmp' : weather['minTmp'],
            'maxTmp' : weather['maxTmp'] ,
            'alertRain' : weather['alertRain'] ,
            'curTmp' : weather['curTmp'] ,
            'humidity' : weather['humidity'] ,
            'sky' : weather['sky'] ,
            'icon' : icon,
            'clothesobject':clothesobject,
            }
        return render(request,"index.html",results)
    except:
        return render(request,"index.html",{ 'clothesobject':clothesobject, })

def get_clothes_recommendation(request):
    user = request.user
    if user.style is None:
        return redirect(f'/mypage/userstyle/{user.first_name}')
    if user.is_authenticated:
        location = get_loc_data()
        weather = get_weather_data()

        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "assistant는 세계 최고의 패션 코디네이터다. 대답은 1000자 이내. 대답 형식은 무조건 첫 시작은 'Clothify의 코디 추천!' 으로 시작해주고, 무조건 존댓말로 말해줘. 주요 내용은 아우터- 상의- 하의- 신발- 가방- 이런 느낌으로 설명해줘. 마지막엔 꼭 !표 붙여줘."
                },
                {
                    "role": "user",
                    "content": f"오늘 {location}의 날씨는 최고 온도는 {weather['maxTmp']}도, 최저 온도는 {weather['minTmp']}도, 현재 기온은 {weather['curTmp']}도, 습도는 {weather['humidity']}%이고, 날씨는 {weather['sky']}이정도야. 내 키는 {user.height}cm에 체중은 {user.weight}kg이고 성별은 {user.sex}자야. 내가 좋아하는 옷의 스타일은 {user.style}이야. 이걸 토대로 오늘의 옷을 코디해줘."
                },
            ]
        )
        answer = completion['choices'][0]['message']['content']

        return JsonResponse({"answer": answer})
    else:
        return JsonResponse({"error": "User not authenticated"})


@login_required(login_url='login')
def view_closet(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    clothesobject = clothes.objects.all()   #clothes의 모든 객체를 c에 담기
    photoobject = photos.objects.all()

    
    if request.method == 'POST':
        del_clothes = request.POST.getlist('del_clothes')   #여러 개의 값 받아오기
        tmp = del_clothes[0].split(",")                     # 받아온 groupID 값 자르기

        if del_clothes:
            for group_id in tmp:
                remove = clothesobject.filter(groupID__exact=group_id)
                remove.delete()
        result = {
                    'clothesobject':clothesobject,
                    'user':user,
                    'photoobject':photoobject,
                }
        return render(request, "view_closet.html", result)
        
            
        #result = {
        #        'clothesobject' : clothesobject,
        #        'photoobject' : photoobject,
        #        'user':user,
        #}
        #return render(request, "view_closet.html", result)
    
    elif request.method == 'GET':
        fl = request.GET.get('fl')  # 필터
        tag = request.GET.get('tagfilter')   #태그

        if not fl and not tag: #검색어가 없으면
            groupIdList = clothesobject.filter(uploadUser__exact=user.id).values_list("groupID") #<QuerySet [('vi3qalsycy',)]>
            photoobject = photoobject.filter(groupID__in = groupIdList).values()
            result = {
                    'clothesobject' : clothesobject,
                    'photoobject' : photoobject,
                    'user':user,
                }
            return render(request, 'view_closet.html', result)
        else:
            q_list=[]                   # 필터링 하기 위한 배열
            filterList=[]

            if(tag):
                tag_filter = clothesobject.filter(tag__contains=tag)
                q_list.append(tag_filter)    
                filterList.append(tag)
                
            # ===== filtering ======
            if fl: #검색어가 있고
                filterList = fl.split(',')
                for item in filterList:
                    if "==" in item:
                        type1Item = item.replace("==","").strip()       # '=='가 포함된 문자열을 ""으로 치환
                        type1_filter = clothesobject.filter(type1__icontains=type1Item)&clothesobject.filter(uploadUser__exact=user.id)    # type1 에서 type1Item 과 대소문자를 가리지 않고 부분 일치하는 조건
                        q_list.append(type1_filter)                     # 조건에 맞은 type1_filter를 q_list에 넣기
                    else:
                        type2_filter = clothesobject.filter(type2__icontains=item)&clothesobject.filter(uploadUser__exact=user.id)
                        q_list.append(type2_filter)
                    
            clothesobject = reduce(or_, q_list).distinct()                          # 타입 검색 -> queryset끼리 중복 제외하고 합쳐짐
            print('q_list',q_list)
            print()
            print('clothesobject',clothesobject.values())
            print()
            result = {
                    'clothesobject':clothesobject,
                    'user':user,
                    'filterList':filterList,
                    'photoobject':photoobject,
                }
            return render(request, 'view_closet.html', result)


    
@login_required(login_url='login')
def uploadCloset(request, username):
    user = get_object_or_404(User, first_name=username) #user = User.objects.get(first_name=username) 예외 처리를 따로 하고 싶을 때 사용
    if user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        getGroupID = request.POST.get('groupID')
        if request.FILES.getlist('imgfile'):
            for imgfile in request.FILES.getlist('imgfile'):
                try:
                    new_clothes =  clothes.objects.filter(Q(groupID__exact = str(getGroupID))).get() # first는 None을 리턴
                # except None:
                except clothes.DoesNotExist or None:
                    try:
                        new_clothes = clothes.objects.create(
                            uploadUser_id=request.user.id,
                            uploadUserName=request.user.username,
                            type1=request.POST.get('type1'),
                            type2=request.POST.get('type2'),
                            tag=request.POST.get('tags'),
                            name=request.POST.get('clothesName'),
                            details=request.POST.get('details'),
                            ucodi=request.POST.get('ucodi'),
                            groupID=getGroupID,
                        )
                        if new_clothes.ucodi == None:
                            new_clothes.ucodi = False
                    except:
                        new_clothes =  clothes.objects.filter(Q(groupID__exact = str(getGroupID))).get() # first는 None을 리턴
                new_clothes.save()
                    
                new_photo = photos.objects.create(
                                groupID_id=new_clothes.groupID,
                                imgfile = imgfile,
                )
                new_photo.save()
        return redirect('view_closet', username=user.first_name)
    else: 
        return render(request, 'upload_closet.html', {"user":user})

@login_required(login_url='login')
def detail_closet(request, username, groupID):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    clothesobject = clothes.objects.filter(Q(groupID__exact=groupID) & Q(uploadUser__exact=user.id)).get()  

    photosobject = photos.objects.annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F('groupID')],
                    order_by=[F('groupID_id')])).order_by('groupID_id')         #order_by 수정

    photosobject = photosobject.filter(groupID__exact=groupID)

    result = {
        'clothesobject' : clothesobject,
        "user" : user,
        "groupID" : groupID,
        'photosobject':photosobject,
    }
    return render(request,"detail_closet.html",result)

@login_required(login_url='login')
def updateCloset(request, username, groupID):
    user = get_object_or_404(User, first_name=username) #user = User.objects.get(first_name=username) 예외 처리를 따로 하고 싶을 때 사용
    if user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        getgroupID = request.POST.get('groupID')
        try:
            new_clothes = clothes.objects.get(groupID__exact = groupID)
            new_clothes.type1 = request.POST.get('type1')
            new_clothes.type2 = request.POST.get('type2')
            new_clothes.tag = request.POST.get('tags')
            new_clothes.name = request.POST.get('clothesName')
            new_clothes.details = request.POST.get('details')
            if request.POST.get('ucodi') == 'True':
                new_clothes.ucodi = True
            else:
                new_clothes.ucodi = False
            new_clothes.save()
        except clothes.DoesNotExist:
            print('객체 오류')
            
        

        if request.FILES.getlist('imgfile'):
            for imgfile in request.FILES.getlist('imgfile'):
                new_photo = photos.objects.create(
                                groupID_id=new_clothes.groupID,
                                imgfile = imgfile,
                )
                new_photo.save()

        return redirect('view_closet', username=user.first_name)
    else:
        clothesobject = clothes.objects.filter(Q(groupID__exact=groupID) & Q(uploadUser__exact=user.id)).get()   
        photosobject = photos.objects.annotate(
                    row_number=Window(
                        expression=RowNumber(),
                        partition_by=[F('groupID')],
                        order_by='groupID_id'
                    )
        )
        photosobject = photosobject.filter(groupID__exact=groupID)
        
        result = {
            "user":user,
            "clothesobject" : clothesobject,
            "groupID" : groupID,
            "photosobject" : photosobject,
        }
        return render(request, 'update_closet.html',result)


@login_required(login_url='login')
def remove_closet(request, username, groupID):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    
    try:
        remove_clothes= clothes.objects.get(groupID=groupID)      # clothes에서 pk와 같은 primary_key 값을 remove_clothes에 담기
        remove_clothes.delete()     # 삭제 후 메시지를 보여줍니다.
        # messages.success(request, '데이터를 삭제했습니다.')
    except clothes.DoesNotExist:
        messages.error(request, '삭제할 데이터가 없습니다.')
    
    return redirect('view_closet', username=user.first_name)

def signup(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == "POST":
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = get_random_string(length=16)
            user.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)  # 사용자 인증
            login(request, user)  # 로그인
            dpath = os.path.join("_media", "imgfiles", "VirtualFitting", "User" , f"{user.first_name}")
            copy = os.path.join("muapp", "VirtualFitting", "Resources", "1.png")

            os.makedirs(os.path.join(dpath, "Shirts"), exist_ok=True)
            os.makedirs(os.path.join(dpath, "Pants"), exist_ok=True)

            shutil.copyfile(copy, os.path.join(dpath, "Shirts", "1.png"))#default사진 복사
            shutil.copyfile(copy, os.path.join(dpath, "Pants", "1.png"))

            messages.success(request, '축하합니다!!\nClothify의 회원가입이 완료되었습니다!')
            return redirect('/')
    else:
        form = UserForm()
    return render(request, 'signup.html', {'form': form,})

def logins(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method =='POST':
        form = LoginForm(request, request.POST)
        if form.is_valid():
            #검증 완료시 로그인
            login(request, form.get_user())
            user = form.get_user().first_name
            if 'next' in request.POST:
                next_string = request.POST.get('next')
                result = next_string.split('/')[1]
                if result == 'modify' or result == 'userlike':
                    return redirect(f'/{result}/')
                elif result == 'usercodi':
                    return redirect(request.POST.get('next'))
                else:
                    print(f'/{result}/{user}')
                    return redirect(f'/{result}/{user}')
            return redirect('/')
    else:
        form = LoginForm()
    return render(request, 'login2.html', {'form': form}) 

@login_required(login_url='login')
def user_modify(request):
    if request.method == 'POST':
        form = ModifyForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('/')
    else:
        form = ModifyForm(instance=request.user)
    return render(request,"user_modify.html", {'form': form,})

@login_required(login_url='login')
def mypage(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    return render(request,"mypage.html",{"user":user})


@login_required(login_url='login')
def codibook(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    if user.style is None:
        return redirect(f'/mypage/userstyle/{user.first_name}')
    userstyle = literal_eval(user.style) # json으로 사용해도됨. 방법:리스트를 JSON 형식으로 직렬화하여 문자열로 저장 userstyle = json.loads(selected_styles)
    musinsa = Musinsa.objects.filter(item_text__in=userstyle)
    paginator = Paginator(musinsa, 9)
    page = request.GET.get('page')
    musinsa = paginator.get_page(page)
    return render(request,"codibook.html",{"user":user, "musinsa":musinsa})

def blog(request):
    return render(request,"blog.html")

def feature(request):
    return render(request,"feature.html")

@login_required(login_url='login')
def user_style(request, username):
    style = ['아메리칸 캐주얼', '캐주얼', '시크', '댄디', '포멀', '걸리시', '골프', '레트로', '로맨틱', '스포츠', '스트릿', '고프코어']
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return redirect('/')
    if request.method == 'POST':
        selected_styles = request.POST.getlist("style")
        if not selected_styles:
            messages.error(request, '적어도 하나 이상의 스타일을 선택해주세요')
            return redirect('user_style', username=username)
        user.style = str(selected_styles) # json으로 사용해도됨. 방법:리스트를 JSON 형식으로 직렬화하여 문자열로 저장 user.style = json.dumps(selected_styles)
        user.save()
        return redirect('/')
    return render(request, "user_style.html", {"user": user, "style": style})

# @login_required(login_url='login')
# def product(request, username):
#     user = User.objects.get(username=username)
#     return render(request,"product.html",{"user":user})


def about(request):
    return render(request, "about.html")


def usercodi(request):
    clothesobject = clothes.objects.filter(ucodi=True)
    paginator = Paginator(clothesobject, 9)
    page = request.GET.get('page')
    clothesobject = paginator.get_page(page)
    comments = Comment.objects.all()
    return render(request,"usercodi.html",{'cloth':clothesobject, 'comments': comments})

def detail_usercodi(request, id):
    clothesobject = clothes.objects.filter(groupID__exact=id).get()  

    comments = Comment.objects.filter(post=clothesobject).order_by('-created_date')

    photosobject = photos.objects.annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F('groupID')],
                    order_by='groupID_id'
                )
    )

    photosobject = photosobject.filter(groupID__exact=id)

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user
            comment.post = clothesobject
            comment.save()
            return redirect('detail_usercodi', id=id)
    else:
        form = CommentForm()

    paginator = Paginator(comments, 5)
    page = request.GET.get('page')
    comments = paginator.get_page(page)

    result = {
        'clothesobject' : clothesobject,
        'photosobject' : photosobject,
        'comments' : comments,
        'form' : form,
    }
    
    return render(request,"detail_usercodi.html", result)

@login_required(login_url='login')
def like(request):
    # 어떤 게시물에, 어떤 사람이 like를 했는 지
   if request.headers.get('X-Requested-With'): #ajax 방식일 때 아래 코드 실행
        groupid = request.GET.get('groupID') #좋아요를 누른 게시물id 가지고 오기
        post = clothes.objects.get(groupID=groupid) 
        user = request.user #request.user : 현재 로그인한 유저
        if post.like.filter(id=user.id).exists(): #이미 좋아요를 누른 유저일 때
            post.like.remove(user) #like field에 현재 유저 추가
        else: #좋아요를 누르지 않은 유저일 때
            post.like.add(user) #like field에 현재 유저 삭제
        # post.like.count() : 게시물이 받은 좋아요 수  
        context = {'like_count' : post.like.count(),}
        return HttpResponse(json.dumps(context), content_type='application/json')
       
@login_required(login_url='login')
def like2(request):
    # 어떤 게시물에, 어떤 사람이 like를 했는 지
   if request.headers.get('X-Requested-With'): #ajax 방식일 때 아래 코드 실행
        cid = request.GET.get('id') #좋아요를 누른 게시물id 가지고 오기
        post = Musinsa.objects.get(id=cid) 
        user = request.user #request.user : 현재 로그인한 유저
        if post.like.filter(id=user.id).exists(): #이미 좋아요를 누른 유저일 때
            post.like.remove(user) #like field에 현재 유저 삭제
        else: #좋아요를 누르지 않은 유저일 때
            post.like.add(user) #like field에 현재 유저 추가
        # post.like.count() : 게시물이 받은 좋아요 수  
        context = {'like_count' : post.like.count(),}
        return HttpResponse(json.dumps(context), content_type='application/json')
   
@login_required(login_url='login')
def virfit(request):
    
    user = request.user
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    cpath = os.path.join(base_dir, "muapp", "VirtualFitting", "Resources")
    dpath = os.path.join(base_dir, "_media", "imgfiles")
    epath = os.path.join(base_dir, "_media", "imgfiles", "VirtualFitting", "User" , f"{user.first_name}")

    pygame.mixer.init()
    shutter_sound = pygame.mixer.Sound(os.path.join(cpath, "shutter.mp3"))
    shutter_sound.set_volume(0.5)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 800)
    detector = PoseDetector()

    shirtsFolderPath = os.path.join(epath, "Shirts")
    pantsFolderPath = os.path.join(epath, "Pants")


    listShirts = os.listdir(shirtsFolderPath)
    listPants = os.listdir(pantsFolderPath)

    fixedRatio = 320 / 190 #셔츠의 넓이 262 / lm11에서 12의 사이 넓이
    shirtsRatioHeight = 500 / 440 #이미지 사이즈 비율 581/440 높이면 작아짐

    fixedRatio2 = 270 / 140 #셔츠의 넓이 262 / lm11에서 12의 사이 넓이
    pantsRatioHeight = 1000 / 440 #이미지 사이즈 비율 581/440

    imageNumber = 0
    imageNumber2 = 0

    cameraButton = cv2.imdecode(np.fromfile(os.path.join(cpath, "camera.png"), np.uint8), cv2.IMREAD_UNCHANGED)
    shirtsButton = cv2.imdecode(np.fromfile(os.path.join(cpath, "shirts.png"), np.uint8), cv2.IMREAD_UNCHANGED)
    pantsButton = cv2.imdecode(np.fromfile(os.path.join(cpath, "pants.png"), np.uint8), cv2.IMREAD_UNCHANGED)
    
    imgButtonRight = cv2.imdecode(np.fromfile(os.path.join(cpath, "button.png"), np.uint8), cv2.IMREAD_UNCHANGED)
    imgButtonLeft = cv2.flip(imgButtonRight, 1)
    counterButton = 0
    counterRight = 0
    counterLeft = 0
    counterRight2 = 0
    counterLeft2 = 0
    counterLeft3 = 0
    counterRight3 = 0
    selectionSpeed = 20
    distance_threshold = 673
    while True:
        success, img = cap.read()
        img = cv2.flip(img, 1)
        img = detector.findPose(img, draw=False)
        lmList, bboxInfo = detector.findPosition(img, bboxWithHands=False, draw=False)
        if bboxInfo:
            # center = bboxInfo["center"]
            # cv2.circle(img, center, 5, (255, 0, 255), cv2.FILLED)

            lm11 = lmList[11][1:3]
            lm12 = lmList[12][1:3]

            lm23 = lmList[23][1:3]
            lm24 = lmList[24][1:3]

            distance = lmList[24][2]
            
            # else:
            #     cv2.putText(img, f"Distance: {distance}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            imgShirt = cv2.imdecode(np.fromfile(os.path.join(shirtsFolderPath, listShirts[imageNumber]), np.uint8), cv2.IMREAD_UNCHANGED)

            imgPant = cv2.imdecode(np.fromfile(os.path.join(pantsFolderPath, listPants[imageNumber2]), np.uint8), cv2.IMREAD_UNCHANGED)



            widthOfShirt = int((lm11[0] - lm12[0]) * fixedRatio)
            widthOfShirt = max(widthOfShirt, 1)#가장 큰값을 반환. wos가 1보다 작아지면 1반환. 0또는 음수가 되면 resize에러 후 종료 방지용
            imgShirt = cv2.resize(imgShirt, (widthOfShirt, int(widthOfShirt * shirtsRatioHeight)))

            widthOfPant = int((lm23[0] - lm24[0]) * fixedRatio2)
            widthOfPant = max(widthOfPant, 1)#가장 큰값을 반환. wos가 1보다 작아지면 1반환. 0또는 음수가 되면 resize에러 후 종료 방지용
            imgPant = cv2.resize(imgPant, (widthOfPant, int(widthOfPant * pantsRatioHeight)))

            currentScale = (lm11[0] - lm12[0]) / 145 #옷 위치 190
            offset = int(50 * currentScale), int(48 * currentScale) #좌우 44, 48 *30/48

            currentScale2 = (lm23[0] - lm24[0]) / 150 #옷 위치 190
            offset2 = int(75 * currentScale2), int(80 * currentScale2) #좌우 44, 48 *30/48 x, y



            try:
                #  img = cvzone.overlayPNG(img, imgShirt, (lm12[0] - offset[0], lm12[1] - offset[1]))
                img_height, img_width, _ = img.shape#웹캠 영상의 높이와 너비를 가져옵니다.
                sh_height, sh_width, _ = imgShirt.shape#셔츠 이미지의 높이와 너비를 가져옵니다.

                x_position = max(0, lm12[0] - offset[0])# 셔츠 이미지의 x 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 왼쪽 경계를 벗어나지 않습니다.
                y_position = max(0, lm12[1] - offset[1])#셔츠 이미지의 y 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 위쪽 경계를 벗어나지 않습니다.

                pa_height, pa_width, _ = imgPant.shape#셔츠 이미지의 높이와 너비를 가져옵니다.

                x_position2 = max(0, lm24[0] - offset2[0])# 셔츠 이미지의 x 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 왼쪽 경계를 벗어나지 않습니다.
                y_position2 = max(0, lm24[1] - offset2[1])#셔츠 이미지의 y 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 위쪽 경계를 벗어나지 않습니다.

                # 셔츠 이미지가 웹캠 영역을 벗어난 경우, 잘라내기
                if x_position2 + pa_width <= img_width and y_position2 + pa_height <= img_height:
                    img = cvzone.overlayPNG(img, imgPant, (x_position2, y_position2))

                if x_position2 + pa_width > img_width or y_position2 + pa_height > img_height:
                    cropped_width2 = min(pa_width, img_width - x_position2)#잘라낼 셔츠 이미지의 너비를 계산합니다. 웹캠 영상의 너비에서 이미지의 x 위치를 뺀 값과 셔츠 이미지의 원래 너비 중 작은 값을 사용합니다.
                    cropped_height2 = min(pa_height, img_height - y_position2)#잘라낼 셔츠 이미지의 높이를 계산합니다. 웹캠 영상의 높이에서 이미지의 y 위치를 뺀 값과 셔츠 이미지의 원래 높이 중 작은 값을 사용합니다.
                    imgPant_cropped = imgPant[:cropped_height2, :cropped_width2]#셔츠 이미지에서 웹캠 영역 안에 있는 부분만 잘라냅니다.
                    img = cvzone.overlayPNG(img, imgPant_cropped, (x_position2, y_position2))#잘라낸 셔츠 이미지를 웹캠 영상에 붙입니다.
                
                if x_position + sh_width <= img_width and y_position + sh_height <= img_height:
                    img = cvzone.overlayPNG(img, imgShirt, (x_position, y_position))

                if x_position + sh_width > img_width or y_position + sh_height > img_height:
                    cropped_width = min(sh_width, img_width - x_position)
                    cropped_height = min(sh_height, img_height - y_position)#
                    imgShirt_cropped = imgShirt[:cropped_height, :cropped_width]
                    img = cvzone.overlayPNG(img, imgShirt_cropped, (x_position, y_position))
                        
                
            except:
                pass
            
            if lmList[15][1] > 1050 and lmList[15][1] < 1200 and lmList[15][2] < 200 and lmList[15][2] > 100:
                counterLeft3 += 1
                cv2.ellipse(img, (1138, 160), (66, 66), 0, 0, 
                            counterLeft3 * selectionSpeed, (0, 255, 0), 20)
                if counterLeft3 * selectionSpeed > 360:
                    counterLeft3 = 0
                    start_time = time.time()
                    countdown = 3

                    while countdown >= 0:
                        _, img = cap.read()
                        img = cv2.flip(img, 1)
                        img = cv2.resize(img, (1280, 720))
                        img = detector.findPose(img, draw=False)
                        lmList, bboxInfo = detector.findPosition(img, bboxWithHands=False, draw=False)
                        if bboxInfo:
                            # center = bboxInfo["center"]
                            # cv2.circle(img, center, 5, (255, 0, 255), cv2.FILLED)

                            lm11 = lmList[11][1:3]
                            lm12 = lmList[12][1:3]

                            lm23 = lmList[23][1:3]
                            lm24 = lmList[24][1:3]

                            distance = lmList[24][2]          
        
                            # else:
                            #     cv2.putText(img, f"Distance: {distance}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                            imgShirt = cv2.imdecode(np.fromfile(os.path.join(epath, os.path.join(shirtsFolderPath, listShirts[imageNumber])), np.uint8), cv2.IMREAD_UNCHANGED)

                            imgPant = cv2.imdecode(np.fromfile(os.path.join(epath, os.path.join(pantsFolderPath, listPants[imageNumber2])), np.uint8), cv2.IMREAD_UNCHANGED)

                            widthOfShirt = int((lm11[0] - lm12[0]) * fixedRatio)
                            widthOfShirt = max(widthOfShirt, 1)#가장 큰값을 반환. wos가 1보다 작아지면 1반환.
                            imgShirt = cv2.resize(imgShirt, (widthOfShirt, int(widthOfShirt * shirtsRatioHeight)))

                            widthOfPant = int((lm23[0] - lm24[0]) * fixedRatio2)
                            widthOfPant = max(widthOfPant, 1)#가장 큰값을 반환. wos가 1보다 작아지면 1반환.
                            imgPant = cv2.resize(imgPant, (widthOfPant, int(widthOfPant * pantsRatioHeight)))

                            currentScale = (lm11[0] - lm12[0]) / 145 #옷 위치 190 내리면 올라감
                            offset = int(50 * currentScale), int(48 * currentScale) #좌우 44, 48 *30/48 왼쪽꺼 내리면 오른쪽으로

                            currentScale2 = (lm23[0] - lm24[0]) / 150 #옷 위치 190
                            offset2 = int(75 * currentScale2), int(80 * currentScale2) #좌우 44, 48 *30/48 x, y



                        # 이 부분에 이미지 처리 코드를 삽입하세요.
                        try:
                            #  img = cvzone.overlayPNG(img, imgShirt, (lm12[0] - offset[0], lm12[1] - offset[1]))
                            img_height, img_width, _ = img.shape#웹캠 영상의 높이와 너비를 가져옵니다.
                            sh_height, sh_width, _ = imgShirt.shape#셔츠 이미지의 높이와 너비를 가져옵니다.

                            x_position = max(0, lm12[0] - offset[0])# 셔츠 이미지의 x 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 왼쪽 경계를 벗어나지 않습니다.
                            y_position = max(0, lm12[1] - offset[1])#셔츠 이미지의 y 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 위쪽 경계를 벗어나지 않습니다.

                            pa_height, pa_width, _ = imgPant.shape#셔츠 이미지의 높이와 너비를 가져옵니다.

                            x_position2 = max(0, lm24[0] - offset2[0])# 셔츠 이미지의 x 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 왼쪽 경계를 벗어나지 않습니다.
                            y_position2 = max(0, lm24[1] - offset2[1])#셔츠 이미지의 y 위치를 계산하되, 0보다 작으면 0으로 설정합니다. 이렇게 하면 이미지가 위쪽 경계를 벗어나지 않습니다.

                            # 셔츠 이미지가 웹캠 영역을 벗어난 경우, 잘라내기
                            if x_position2 + pa_width <= img_width and y_position2 + pa_height <= img_height:
                                img = cvzone.overlayPNG(img, imgPant, (x_position2, y_position2))

                            if x_position2 + pa_width > img_width or y_position2 + pa_height > img_height:
                                cropped_width2 = min(pa_width, img_width - x_position2)#잘라낼 셔츠 이미지의 너비를 계산합니다. 웹캠 영상의 너비에서 이미지의 x 위치를 뺀 값과 셔츠 이미지의 원래 너비 중 작은 값을 사용합니다.
                                cropped_height2 = min(pa_height, img_height - y_position2)#잘라낼 셔츠 이미지의 높이를 계산합니다. 웹캠 영상의 높이에서 이미지의 y 위치를 뺀 값과 셔츠 이미지의 원래 높이 중 작은 값을 사용합니다.
                                imgPant_cropped = imgPant[:cropped_height2, :cropped_width2]#셔츠 이미지에서 웹캠 영역 안에 있는 부분만 잘라냅니다.
                                img = cvzone.overlayPNG(img, imgPant_cropped, (x_position2, y_position2))#잘라낸 셔츠 이미지를 웹캠 영상에 붙입니다.
                            
                            if x_position + sh_width <= img_width and y_position + sh_height <= img_height:
                                img = cvzone.overlayPNG(img, imgShirt, (x_position, y_position))

                            if x_position + sh_width > img_width or y_position + sh_height > img_height:
                                cropped_width = min(sh_width, img_width - x_position)
                                cropped_height = min(sh_height, img_height - y_position)#
                                imgShirt_cropped = imgShirt[:cropped_height, :cropped_width]
                                img = cvzone.overlayPNG(img, imgShirt_cropped, (x_position, y_position))      
                            
                        except:
                            pass

                        elapsed_time = time.time() - start_time
                        if elapsed_time >= 1:
                            countdown -= 1
                            start_time = time.time()

                        if countdown != -1:
                            img_pil = Image.fromarray(img)
                            draw = ImageDraw.Draw(img_pil)
                            font = ImageFont.truetype(os.path.join(cpath, "GmarketSansTTF\GmarketSansTTFBold.ttf"), 80)
                            text = f"{countdown}"
                            position = (580, 10)
                            border_color = (0, 0, 0)  # 검은색 테두리
                            fill_color = (0, 255, 0, 0)  # 초록색 내부 색상
                            border_width = 1  # 테두리 두께

                            # 텍스트 주위에 테두리를 그립니다.
                            for x_offset in range(-border_width, border_width + 1):
                                for y_offset in range(-border_width, border_width + 1):
                                    draw.text((position[0] + x_offset, position[1] + y_offset), text, font=font, fill=border_color)

                            # 텍스트를 그립니다.
                            draw.text(position, text, font=font, fill=fill_color)
                            img = np.array(img_pil)

                        cv2.imshow("Virtual Fitting", img)
                        cv2.waitKey(1)

                    shutter_sound.play()
                    white_img = np.full(img.shape, 255, dtype=np.uint8)
                    cv2.imshow("Virtual Fitting", white_img)
                    cv2.waitKey(200)
                    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                    
                    os.makedirs(os.path.join(dpath, "VirtualFitting"), exist_ok=True)
                    os.makedirs(os.path.join(dpath, "VirtualFitting", "User"), exist_ok=True)
                    os.makedirs(os.path.join(dpath, "VirtualFitting", "User", f"{user.first_name}"), exist_ok=True)
                    os.makedirs(os.path.join(dpath, "VirtualFitting", "User", f"{user.first_name}", "Capture"), exist_ok=True)
                    new_img_name = os.path.join(dpath, rf"VirtualFitting\User\{user.first_name}\Capture\capture_{timestamp}.png")
                    extension = os.path.splitext(new_img_name)[1]
                    result, encoded_img = cv2.imencode(extension, img)

                    if result:
                        with open(new_img_name, mode='w+b') as f:
                            encoded_img.tofile(f)
                            new_clothes = clothes.objects.create(
                            uploadUser_id=user.id,
                            uploadUserName=user.username,
                            type1='가상피팅',
                            type2='코디',
                            name=f'{user.username}-{timestamp}',
                            ucodi=False,
                            tag='#가상피팅',
                            groupID=get_random_string(length=10, allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789'),
                        )
                            new_clothes.save()
                            
                            new_photo = photos.objects.create(
                                    groupID_id=new_clothes.groupID,
                                    imgfile = rf'imgfiles\VirtualFitting\User\{user.first_name}\Capture\capture_{timestamp}.png',
                            )
                            new_photo.save()


                    print("Capture saved")

            else:
                counterLeft3 = 0


            img_pil = Image.fromarray(img)
            draw = ImageDraw.Draw(img_pil)
            font = ImageFont.truetype(os.path.join(cpath, "GmarketSansTTF\GmarketSansTTFBold.ttf"), 30)  # 한글 폰트 파일을 사용합니다. 시스템에 따라 경로를 변경해야 할 수도 있습니다.
            text = "좌우 버튼을 눌러서 가상피팅을 해보세요!(나가기-Q)"
            position = (580, 10)
            border_color = (0, 0, 0)  # 검은색 테두리
            fill_color = (0, 255, 0, 0)  # 초록색 내부 색상
            border_width = 1  # 테두리 두께

            # 텍스트 주위에 테두리를 그립니다.
            for x_offset in range(-border_width, border_width + 1):
                for y_offset in range(-border_width, border_width + 1):
                    draw.text((position[0] + x_offset, position[1] + y_offset), text, font=font, fill=border_color)

            # 텍스트를 그립니다.
            draw.text(position, text, font=font, fill=fill_color)
            img = np.array(img_pil)

            # if distance > distance_threshold:
            #     img_pil = Image.fromarray(img)
            #     draw = ImageDraw.Draw(img_pil)
            #     font = ImageFont.truetype(f"{cpath}GmarketSansTTF\GmarketSansTTFBold.ttf", 30)  # 한글 폰트 파일을 사용합니다. 시스템에 따라 경로를 변경해야 할 수도 있습니다.
            #     draw.text((10, 10), "너무 가깝습니다.", font=font, fill=(0, 0, 255, 0))
            #     img = np.array(img_pil)

            img = cvzone.overlayPNG(img, cameraButton, (1074, 93))

            if counterButton == 0:
                img = cvzone.overlayPNG(img, shirtsButton, (72, 93))
            elif counterButton == 1:
                img = cvzone.overlayPNG(img, pantsButton, (72, 93))

            img = cvzone.overlayPNG(img, imgButtonRight, (1074, 293))
            img = cvzone.overlayPNG(img, imgButtonLeft, (72, 293))

            # img = cvzone.overlayPNG(img, imgButtonRight, (1074, 493))
            # img = cvzone.overlayPNG(img, imgButtonLeft, (72, 493))

            
            if lmList[16][1] < 200 and lmList[16][1] > 100 and lmList[16][2] < 200 and lmList[16][2] > 100:
                counterRight3 += 1
                cv2.ellipse(img, (134, 160), (76, 76), 0, 0, 
                            counterRight3 * selectionSpeed, (0, 255, 0), 20)
                if counterRight3 * selectionSpeed > 360:
                    counterRight3 = 0
                    if counterButton == 0:
                        counterButton = 1
                    else:
                        counterButton = 0

            if counterButton == 0:
                if lmList[16][1] < 200 and lmList[16][1] > 100 and lmList[16][2] < 400 and lmList[16][2] > 300:
                    counterRight += 1
                    cv2.ellipse(img, (139, 360), (66, 66), 0, 0, 
                                counterRight * selectionSpeed, (0, 255, 0), 20)
                    if counterRight * selectionSpeed > 360:
                        counterRight = 0
                        if imageNumber < len(listShirts)-1:
                            imageNumber += 1
                        else:
                            imageNumber = 0

                elif lmList[15][1] > 1050 and lmList[15][1] < 1200 and lmList[15][2] < 400 and lmList[15][2] > 300:
                    counterLeft += 1
                    cv2.ellipse(img, (1138, 360), (66, 66), 0, 0, 
                                counterLeft * selectionSpeed, (0, 255, 0), 20)
                    if counterLeft * selectionSpeed > 360:
                        counterLeft = 0
                        if imageNumber > 0:
                            imageNumber -= 1
                        else:
                            imageNumber = len(listShirts)-1
                else:
                    counterRight = 0
                    counterLeft = 0
            
            elif counterButton == 1:
                if lmList[16][1] < 200 and lmList[16][1] > 100 and lmList[16][2] < 400 and lmList[16][2] > 300:
                    counterRight2 += 1
                    cv2.ellipse(img, (139, 360), (66, 66), 0, 0, 
                                counterRight2 * selectionSpeed, (0, 255, 0), 20)
                    if counterRight2 * selectionSpeed > 360:
                        counterRight2 = 0
                        if imageNumber2 < len(listPants)-1:
                            imageNumber2 += 1
                        else:
                            imageNumber2 = 0

                elif lmList[15][1] > 1050 and lmList[15][1] < 1200 and lmList[15][2] < 400 and lmList[15][2] > 300:
                    counterLeft2 += 1
                    cv2.ellipse(img, (1138, 360), (66, 66), 0, 0, 
                                counterLeft2 * selectionSpeed, (0, 255, 0), 20)
                    if counterLeft2 * selectionSpeed > 360:
                        counterLeft2 = 0
                        if imageNumber2 > 0:
                            imageNumber2 -= 1
                        else:
                            imageNumber2 = len(listPants)-1
                else:
                    counterRight2 = 0
                    counterLeft2 = 0

            

        cv2.imshow("Virtual Fitting", img)

        key = cv2.waitKey(1)

        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    return redirect('virtual_fit_video', user.first_name)


@login_required(login_url='login')
def virtual_fit_photo(request,username):
    user = request.user
    model_dataset = viton_upload_model.objects.all()
    model_paginator = Paginator(model_dataset, 20)
    model_page = request.GET.get('mpage')
    model_paging = model_paginator.get_page(model_page)
    
    cloth_dataset = viton_upload_cloth.objects.all()
    cloth_paginator = Paginator(cloth_dataset, 20)
    cloth_page = request.GET.get('cpage')
    cloth_paging = cloth_paginator.get_page(cloth_page)

    del_model = request.POST.getlist('del_model')     # 여러 개의 값 받아오기
    del_cloth = request.POST.getlist('del_cloth')     
    
    
    if del_model:
        tmp = del_model[0].split(",")                     # 받아온 name 값 자르기
        for model_name in tmp:
            remove_model = model_dataset.filter(ID__exact=model_name)
            remove_model.delete()
        
    if del_cloth:
        tmp2 = del_cloth[0].split(",")
        for cloth_name in tmp2:
            remove_cloth = cloth_dataset.filter(ID__exact=cloth_name)
            remove_cloth.delete()    

    result = {    
                'model_paging' : model_paging,
                'cloth_paging' : cloth_paging,
            }
    return render(request, "virtual_fit_photo.html", result)
    
    

@login_required(login_url='login')
def virtual_fit_photo_result(request,username):
    user = request.user
    if request.method == 'POST':
        model_result = request.POST.getlist('model_result')
        cloth_result = request.POST.getlist('cloth_result')

        selected_model = model_result[0].split(",")
        selected_cloth = cloth_result[0].split(",")
        
        print(model_result)
        print(cloth_result)
                          
        q_list=[]
        file_list_file = os.path.join('muapp','viton','data','custom','custom_pairs.txt')
        
        custompath = os.path.join("muapp","viton","data","custom")
        if os.path.exists(custompath):
            shutil.rmtree(custompath)

        imagepath = os.path.join(custompath,"image")
        maskpath = os.path.join(custompath,"image-parse")
        openposeIpath = os.path.join(custompath,"openpose-img")
        openposeJpath = os.path.join(custompath,"openpose-json")
        clothpath = os.path.join(custompath,"cloth")
        clothmaskpath = os.path.join(custompath,"cloth-mask")

        if not os.path.exists(custompath):
            os.mkdir(custompath)

        if not os.path.exists(imagepath):
            os.mkdir(imagepath)

        if not os.path.exists(maskpath):
            os.mkdir(maskpath)

        if not os.path.exists(openposeIpath):
            os.mkdir(openposeIpath)

        if not os.path.exists(openposeJpath):
            os.mkdir(openposeJpath)

        if not os.path.exists(clothpath):
            os.mkdir(clothpath)    

        if not os.path.exists(clothmaskpath):
            os.mkdir(clothmaskpath)    


        with open(file_list_file, 'w') as f:
            for model in selected_model:
                models_obj = viton_upload_model.objects.filter(ID__exact=int(model))
                model_obj = models_obj.first()
                model_name = model_obj.name
                model_name_split = model_name.split('.')
                shutil.copyfile(os.path.join('_media','datasets','image',model_name), os.path.join(imagepath,model_name)) #_media -> viton data로 복사
                
                if not model_obj.maskmodel: #model의 mask가 없으면
                # if (model_obj.maskmodel is None) or (model_obj.openposeImage is None) or (model_obj.openposeJson is None): #model의 mask가 없으면
                    print('model_obj', model_obj, 'is not exist')
                    #image-parse 
                    try:
                        os.system(f"python ../Self-Correction-Human-Parsing/simple_extractor.py --dataset lip --model-restore C:/hs-grad-2023/django/muapp/viton/checkpoints/human_parsing_final.pth --input-dir {imagepath} --output-dir {maskpath}")
                    except:
                        raise    
                    print('Image Parsing Done..')

                    mask_file = open(os.path.join(maskpath,model_name_split[0]+'.png'),'rb')
                    model_obj.maskmodel.save(model_name_split[0]+'.png',File(mask_file),save=True)
                    
                    #openpose-image, openpose-json
                    os.chdir("../openpose_demo")
                    try:
                        os.system(f"bin\\OpenPoseDemo.exe --image_dir ..\\django\\{imagepath} --hand --disable_blending --display 0 --write_json ..\\django\\{openposeJpath} --write_images  ..\\django\\{openposeIpath} --num_gpu 1 --num_gpu_start 0")
                    except:
                        raise
                    print('openpose Making Done..')

                    os.chdir("../django")
                    opimg_file = open(os.path.join(openposeIpath,model_name_split[0]+'_rendered.png'),'rb')
                    model_obj.openposeImage.save(model_name_split[0]+'_rendered.png',File(opimg_file),save=True)

                    opjson_file = open(os.path.join(openposeJpath,model_name_split[0]+'_keypoints.json'),'rb')
                    model_obj.openposeJson.save(model_name_split[0]+'_keypoints.json',File(opjson_file),save=True)

                else: # model의 mask가 있을때
                    shutil.copyfile(os.path.join('_media','datasets','image-parse',os.path.basename(model_obj.maskmodel.url)), os.path.join(maskpath,model_name_split[0]+'.png')) #_media -> viton data로 복사
                    shutil.copyfile(os.path.join('_media','datasets','openpose-img',os.path.basename(model_obj.openposeImage.url)), os.path.join(openposeIpath,model_name_split[0]+'_rendered.png')) #_media -> viton data로 복사
                    shutil.copyfile(os.path.join('_media','datasets','openpose-json',os.path.basename(model_obj.openposeJson.url)), os.path.join(openposeJpath,model_name_split[0]+'_keypoints.json')) #_media -> viton data로 복사
                    
                for cloth in selected_cloth:
                    clothes_obj = viton_upload_cloth.objects.filter(ID__exact=int(cloth))
                    cloth_obj = clothes_obj.first()
                    cloth_name = cloth_obj.name
                    impath = os.path.join('_media','datasets','cloth',cloth_name)
                    shutil.copyfile(os.path.join('_media','datasets','cloth',cloth_name), os.path.join(clothpath,cloth_name)) #_media -> viton data로 복사


                    if not cloth_obj.maskimage: #cloth의 mask데이터가 없을 때
                        cloth_obj = clothes_obj.first()
                        impath = os.path.join('_media','datasets','cloth',cloth_name)

                        clothmask.cloth_mask(img_dir=os.path.join(clothpath,cloth_name),result_dir=clothmaskpath) #cloth-mask 생성

                        mask_file = open(os.path.join(clothmaskpath,cloth_name),'rb') #cloth-mask db저장
                        cloth_obj.maskimage.save(cloth_name,File(mask_file),save=True)
                    else: #cloth의 mask가 있을때 건너뜀
                        shutil.copyfile(os.path.join('_media','datasets','cloth-mask',cloth_name), os.path.join(clothmaskpath, cloth_name)) #_media -> viton data로 복사

                    result_obj = viton_upload_result.objects.filter(Q(model_id__exact=int(model)),Q(cloth_id__exact=int(cloth)))
                    if not result_obj.exists(): #만들어진 결과가 없으면 

                        # viton용 txt 파일 생성
                        result_name = model_name + ' ' + cloth_name
                        f.write(result_name + '\n')

        f.close()

        # 업로드한 사진 + 모델들 합성해서 결과 만들기
        os.chdir('muapp/viton')
        os.system("python custom.py --name output")
        os.chdir("../../")

        # 결과 DB 업로드
        result_dir = os.path.join(custompath,"results","output")
        
        for root, dirs, files in os.walk(result_dir):
            for result in files:
                # 이미지 파일 경로 생성
                result_path = os.path.join(root, result)
                # 모델 인스턴스 생성 및 저장
                values = re.split('[_|.]',result)
                
                model_val = viton_upload_model.objects.filter(name__contains=values[0])
                cloth_val = viton_upload_cloth.objects.filter(name__contains=values[1])

                model_obj = model_val.first()
                cloth_obj = cloth_val.first()

                model_id = model_obj.ID
                cloth_id = cloth_obj.ID
                with open(result_path, 'rb') as f:
                    file = SimpleUploadedFile(f.name, f.read())

                # 모델 인스턴스 생성 및 저장
                result = viton_upload_result(name=result, image=file, model_id=model_id, cloth_id=cloth_id, uploadUser=request.user.username)
                result.save()
        
        # 업로드 완료한 결과 폴더 삭제
        #shutil.rmtree(result_dir)

        for model in selected_model:
            for cloth in selected_cloth:
                filtered = viton_upload_result.objects.filter(Q(model_id__exact=int(model)),Q(cloth_id__exact=int(cloth)))
                q_list.append(filtered)
        
        result_viton = reduce(or_, q_list).distinct()       # 타입 검색 -> queryset끼리 중복 제외하고 합쳐짐
        result = {"user":user,
                  "result_viton":result_viton,
                  "selected_cloth" : selected_cloth,
                  "selected_model" : selected_model,
                  }

        return render(request, "virtual_fit_photo_result.html",result)
    else:
        return redirect('virtual_fit_photo', username=user.first_name)

@login_required(login_url='login')
def virtual_fit_save(request,username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        result_ids = request.POST.getlist('resultID')
        for r in result_ids:
            result_obj = viton_upload_result.objects.filter(id__exact=int(r)).first()
            new_clothes = clothes.objects.create(
                            uploadUser_id=user.id,
                            uploadUserName=user.username,
                            type1='가상피팅',
                            type2='상의',
                            name=f'상의-{r}',
                            ucodi=False,
                            tag='#가상피팅',
                            groupID=get_random_string(length=10, allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789'),
                        )
                    
            new_photo = photos.objects.create(
                groupID_id=new_clothes.groupID,
                imgfile = result_obj.image,
        )
            
        new_clothes.save()
        new_photo.save()
        return redirect(f'/view_closet/{request.user.first_name}')
    return redirect(f'/virtual_fit_result/{request.user.first_name}')

@login_required(login_url='login')
def virtual_fit_video(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return redirect(f'/virtual_fit_video/{request.user.first_name}')
    return render(request,"virtual_fit_video.html",{"user":user})

@login_required(login_url='login')
def virtual_fit_upload(request,username):
    user = request.user
    if user != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        if request.FILES.getlist('imgfile'):
            getType = request.POST.get('itemtype')
            if getType == '옷':
                for imgfile in request.FILES.getlist('imgfile'):
                    # 조정된 이미지 저장
                    item = viton_upload_cloth.objects.create(
                        clothesname = request.POST.get('itemName'),
                        image=imgfile,
                        uploadUser=request.user.username,
                    )
                    item.save()

                    impath = os.path.join('_media','datasets','cloth',item.name)
                    clothmaskpath = os.path.join("muapp","viton","data","custom","cloth-mask")
                    clothpath = os.path.join("muapp","viton","data","custom","cloth")

                    clothmask.cloth_mask(img_dir=impath,result_dir=clothmaskpath) #cloth-mask 생성
                    
                    #cloth-mask db저장
                    mask_file = open(os.path.join(clothmaskpath,item.name),'rb') 
                    item.maskimage.save(item.name,File(mask_file),save=True)

                    #옷 정보만 남기는 cloth파일 작성
                    img = cv2.imread(impath)
                    mask = cv2.imread(os.path.join(clothmaskpath,item.name), 0)  # 이진 마스크는 흑백 이미지이므로 0으로 읽어옵니다.

                    # 이진 마스크에 따라 이미지에서 원하는 부분을 선택합니다.
                    result = cv2.bitwise_and(img, img, mask=mask)
                    
                    mask_inv = cv2.bitwise_not(mask)
                    white_bg = np.full(img.shape, (255, 255, 255), dtype=np.uint8)
                    white_bg_masked = cv2.bitwise_and(white_bg, white_bg, mask=mask_inv)
                    result = cv2.add(result, white_bg_masked)

                    cv2.imwrite(os.path.join(clothpath,item.name), result)
                    cv2.imwrite(impath, result)
                    #옷 정보만 남긴 cloth 파일로 대체
                    #shutil.copyfile(os.path.join(clothpath,item.name),impath) #_media -> viton data로 복사
                    #cloth_file = open(os.path.join(clothpath,cloth_name),'rb') 
                    #cloth_obj.image.save(cloth_name,File(cloth_file),save=False)

            elif getType == '모델':
                for imgfile in request.FILES.getlist('imgfile'):
                    item = viton_upload_model.objects.create(
                        name=request.POST.get('itemName'),
                        image = imgfile,
                        uploadUser=request.user.username,
                    )
                    item.save()

        return redirect('virtual_fit_photo', username=user.first_name)
        #return render(request,"virtual_fit_upload.html", {"user":user})
    else: 
        return render(request,"virtual_fit_upload.html", {"user":user})

@login_required(login_url='login')
def userlike(request):
    user = request.user
    clothesobject = user.likes.all()
    paginator = Paginator(clothesobject, 9)
    page = request.GET.get('page')
    clothesobject = paginator.get_page(page)
    comments = Comment.objects.all()
    
    musinsa = user.likes2.all()
    paginator = Paginator(musinsa, 9)
    page = request.GET.get('page')
    musinsa = paginator.get_page(page)
    return render(request,"userlike.html",{'cloth':clothesobject, 'comments': comments, 'musinsa': musinsa,})


sam_checkpoint = os.path.join("checkpoint", "sam_vit_h_4b8939.pth")
model_type = "vit_h"
device = "cuda"

sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
sam.to(device=device)

predictor = SamPredictor(sam)

def convert_png_to_jpg(image_file):
    # 이미지 파일 열기
    img = Image.open(image_file)

    # 알파 채널이 있는 경우, 알파 채널을 제거하고 배경색을 흰색으로 설정
    if img.mode == "RGBA":
        img = img.convert("RGB")

    # 이미지를 BytesIO 객체로 저장
    img_bytes = BytesIO()
    img.save(img_bytes, "JPEG", quality=95) # 포인터가 데이터 끝으로 이동하게됨 끝으로 가면 읽어오지를 못함
    img_bytes.seek(0) #포인터 시작지점으로 되돌림

    # BytesIO 객체를 ContentFile 객체로 변환 메모리상의 데이터로부터 파일 객체를 생성
    jpg_image = ContentFile(img_bytes.read(), image_file.name)

    return jpg_image


@login_required(login_url='login')
def segment_image(request):
    user = request.user
    if request.method == 'POST':
        checked = request.POST.get('cloth')

        # 이미지를 업로드해서 사용하는 경우
        image_file = request.FILES['image']
        if image_file.name.split(".")[1] == 'png':
            image_file = convert_png_to_jpg(image_file)
            image = Image.open(image_file)
        else:
            image = Image.open(image_file)
        image = np.array(image)

        # 예측할 좌표 설정
        input_point_str = request.POST['input_point']
        input_point = np.array(json.loads(input_point_str)).reshape(1, -1)
        input_label = np.array([1])

        # 이미지 분할
        predictor.set_image(image)
        masks, scores, logits = predictor.predict(
            point_coords=input_point,
            point_labels=input_label,
            multimask_output=True,
        )
        middle_index = np.argmax(scores)

        mask1 = masks[middle_index]
        mask1_3ch = np.stack([mask1, mask1, mask1], axis=-1)
        masked_image = image * mask1_3ch

        mask1_alpha = np.stack([mask1, mask1, mask1, mask1], axis=-1)
        masked_image_alpha = np.concatenate([image, 255 * np.ones((*image.shape[:2], 1), dtype=np.uint8)], axis=-1) * mask1_alpha

        # 마스크 영역의 경계를 찾습니다.
        y, x = np.where(mask1 == 1)
        y_min, y_max, x_min, x_max = np.min(y), np.max(y), np.min(x), np.max(x)

        # 이미지를 자릅니다.
        cropped_image_alpha = masked_image_alpha[y_min:y_max+1, x_min:x_max+1, :]


        # 결과 이미지를 서버의 output_images 폴더에 저장합니다.
        output_image = Image.fromarray(np.uint8(cropped_image_alpha), mode='RGBA')
        if checked == 'tops':
            output_folder = os.path.join("_media", "imgfiles", "VirtualFitting", "User" , f"{user.first_name}", "Shirts") 
            
        elif checked == 'bottoms':
            output_folder = os.path.join("_media", "imgfiles", "VirtualFitting", "User" , f"{user.first_name}", "Pants")
        os.makedirs(output_folder, exist_ok=True)
        file_names = os.listdir(output_folder)

        max_num = 0
        for name in file_names:
            try:
                num = int(name.split('.')[0])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass

     
        times = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_filename = f'{max_num + 1}.png'
        output_filepath = os.path.join(output_folder, output_filename)
        output_image.save(output_filepath)

        if checked == 'tops':
            new_clothes = clothes.objects.create(
                                uploadUser_id=user.id,
                                uploadUserName=user.username,
                                type1='가상피팅',
                                type2='상의',
                                name=f'상의-{output_filename.split(".")[0]}',
                                ucodi=False,
                                tag='#가상피팅',
                                groupID=get_random_string(length=10, allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789'),
                            )
            
            new_photo = photos.objects.create(
                groupID_id=new_clothes.groupID,
                imgfile = rf'imgfiles\VirtualFitting\User\{user.first_name}\Shirts\{output_filename}',
        )
        elif checked == 'bottoms':
            new_clothes = clothes.objects.create(
                                uploadUser_id=user.id,
                                uploadUserName=user.username,
                                type1='가상피팅',
                                type2='하의',
                                name=f'하의-{output_filename.split(".")[0]}',
                                ucodi=False,
                                tag='#가상피팅',
                                groupID=get_random_string(length=10, allowed_chars='abcdefghijklmnopqrstuvwxyz0123456789'),
                            )
                        
            new_photo = photos.objects.create(
                groupID_id=new_clothes.groupID,
                imgfile = rf'imgfiles\VirtualFitting\User\{user.first_name}\Pants\{output_filename}',
        )
            
        new_clothes.save()
        new_photo.save()

        return JsonResponse({'result': f'저장 완료!'})
    else:
        clothesobject = clothes.objects.filter(type1__contains='가상피팅', type2__contains='상의')   #clothes의 모든 객체를 c에 담기
        clothesobject2 = clothes.objects.filter(type1__contains='가상피팅', type2__contains='하의')   #clothes의 모든 객체를 c에 담기
        
        # GET 요청에 대한 처리 (예: 폼 렌더링)
        return render(request, 'segment_image.html', {'clothesobject':clothesobject,'clothesobject2':clothesobject2, 'user':user})
