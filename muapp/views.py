from sqlite3 import IntegrityError
import sqlite3
import sys
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from .api import get_loc_data, get_time, get_weather_data, get_icon
from .models import clothes, photos, Musinsa, Comment
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
from PIL import Image
from itertools import chain
from django.views.decorators.http import require_POST

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
}

allTypeCategory = [ "== 상의 ==", "== 하의 ==","== 치마 ==","== 원피스 ==","== 아우터 ==","== 가방 ==","== 악세서리 ==","== 신발 =="]

@receiver(user_signed_up)
def add_social_user_name(sender, request, user, **kwargs):
    social_accounts = SocialAccount.objects.get(user=user)
    user.first_name = get_random_string(length=16)
    if social_accounts.provider == 'kakao':
        user.name = social_accounts.extra_data['properties']['nickname']
    else:
        user.name = social_accounts.extra_data['name']
    user.save()
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

@login_required(login_url='login')
def view_closet(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return HttpResponseForbidden()
    clothesobject = clothes.objects.all()   #clothes의 모든 객체를 c에 담기
    photoobject = photos.objects.all()

    del_clothes = request.POST.getlist('delete_clothes')
    if del_clothes:
        for group_id in del_clothes:
            remove = clothesobject.get(groupID=group_id)
            remove.delete()


    # ===== filtering ======
    fl = request.GET.get('fl')  # 검색어
    if fl: #검색어가 있고
        filterList = fl.split(',')
        q_list=[]                   # 필터링 하기 위한 배열
        for item in filterList:
            if "==" in item:
                type1Item = item.replace("==","").strip()       # '=='가 포함된 문자열을 ""으로 치환
                type1_filter = clothesobject.filter(type1__icontains=type1Item)&clothesobject.filter(uploadUser__exact=user.id)    # type1 에서 type1Item 과 대소문자를 가리지 않고 부분 일치하는 조건
                q_list.append(type1_filter)                     # 조건에 맞은 type1_filter를 q_list에 넣기
            else:
                type2_filter = clothesobject.filter(type2__icontains=item)&clothesobject.filter(uploadUser__exact=user.id)
                q_list.append(type2_filter)
            
            
        #clothesobject = clothesobject.filter(reduce(or_, q_list)).distinct()   # 타입 검색 -> queryset끼리 중복 제외하고 합병( 조건부 표현식에 대해 필터링 할 수 없다고 뜸)
            
        clothesobject = reduce(or_, q_list).distinct()                          # 타입 검색 -> queryset끼리 중복 제외하고 합쳐짐
        
        result = {
                'clothesobject':clothesobject,
                'user':user,
                'filterList':filterList,
                'photoobject':photoobject,
            }
        return render(request, 'view_closet.html', result)
    else: #검색어가 없으면
        groupIdList = clothesobject.filter(uploadUser__exact=user.id).values_list("groupID") #<QuerySet [('vi3qalsycy',)]>
        photoobject = photoobject.filter(groupID__in = groupIdList).values()
        result = {
                'clothesobject' : clothesobject,
                'photoobject' : photoobject,
                'groupIdList' : groupIdList,
                'user':user,
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
                    order_by='groupID_id'
                )
    )

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
            messages.success(request, '축하합니다!!\nClothify의 회원가입이 완료되었습니다!')
            return redirect('/')
    else:
        form = UserForm()
    return render(request, 'signup.html', {'form': form})

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
                if result == 'modify':
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
def virtual_fit(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return redirect(f'/virtual_fit/{request.user.first_name}')
    return render(request,"virtual_fit.html",{"user":user})

@login_required(login_url='login')
def virtual_fit_upload(request, username):
    user = get_object_or_404(User, first_name=username)
    if user != request.user:
        return redirect(f'/virtual_fit_upload/{request.user.first_name}')
    if request.method == 'POST':
        if request.FILES.getlist('imgfile'):
            for imgfile in request.FILES.getlist('imgfile'):
                try:
                    new_clothes = clothes.objects.create(
                        uploadUser_id=request.user.id,
                        uploadUserName=request.user.username,
                        type1=request.POST.get('type1'),
                        type2=request.POST.get('type2'),
                        tag=request.POST.get('tags'),
                        name=request.POST.get('clothesName'),
                        details=request.POST.get('details'),
                    )
                except:
                    print()
                new_clothes.save()

        return redirect('view_closet', username=user.first_name)
    else: 
        return render(request,"virtual_fit_upload.html",{"user":user})


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

