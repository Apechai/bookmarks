# Create your views here.

from django.http import HttpResponse, Http404
from django.http import HttpResponseRedirect
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.template import RequestContext
from django.template.loader import get_template
from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
from bookmarks.forms import *
from bookmarks.models import *


def main_page(request):
	shared_bookmarks = SharedBookmark.objects.order_by('-date')[:10]
	variables = RequestContext(request, {'shared_bookmarks': shared_bookmarks})
	return render_to_response('main_page.htm',
		variables)

def user_page(request, username):
	user = get_object_or_404(User, username=username)
	bookmarks = user.bookmark_set.order_by('-id')
	if request.user.is_authenticated():
		is_friend = Friendship.objects.filter(
			from_friend=request.user,
			to_friend=user)
	else:
		is_friend = False
	variables = RequestContext(request,
	{
		'username': username,
		'bookmarks': bookmarks,
		'show_tags': True,
		'show_edit': username == request.user.username,
		'is_friend': is_friend,
	})
	return render_to_response('user_page.htm',
		variables)

def logout_page(request):
	logout(request)
	return HttpResponseRedirect('/')
	
def register_page(request):
	if request.method == 'POST':
		form = RegistrationForm(request.POST)
		if form.is_valid():
			user = User.objects.create_user(
			username = form.cleaned_data['username'],
			password = form.cleaned_data['password1'],
			email = form.cleaned_data['email'])
			if 'invitation' in request.session:
				# Retrieve the invitation object
				invitation = Invitation.objects.get(
					id = request.session['invitation'])
				# Create friendship from user to sender.
				friendship = Friendship(
					from_friend=user,
					to_friend=invitation.sender)
				friendship.save()
				# Create friendhip from sender to user.
				friendship = Friendship(
					from_friend=invitation.sender,
					to_friend=user)
				friendship.save()
				# Delete the invitation from the database and session.
				invitation.delete()
				del request.session['invitation']
			return HttpResponseRedirect('/register/success/')
	else:
		form = RegistrationForm()
	variables = RequestContext(request, {'form': form})
	return render_to_response('registration/register.htm', variables)

@login_required
def bookmark_save_page(request):
	ajax = request.GET.has_key('ajax')
	
	if request.method == 'POST':
		form = BookmarkSaveForm(request.POST)
		if form.is_valid():
			bookmark = _bookmark_save(request, form)
			if ajax: 
				variables = RequestContext(request,
					{
					'bookmarks': [bookmark],
					'show_edit': True,
					'show_tags': True
					})
				return render_to_response(
					'bookmark_list.htm', variables)
			else:
				return HttpResponseRedirect(
					'/user/%s/' % request.user.username)
			
		else:
			if ajax:
				return HttpResponse(u'failure')
	elif 'url' in request.GET:
		url = request.GET['url']
		title = ''
		tags = ''
		try:
			link = Link.objects.get(url=url)
			bookmark = Bookmark.objects.get(
				link=link,
				user=request.user
			)
			title = bookmark.title
			tags = ' '.join(tag.name for tag in bookmark.tag_set.all())
		except (Link.DoesNotExist, Bookmark.DoesNotExist): 
			pass
		form = BookmarkSaveForm({
			'url': url,
			'title': title,
			'tags': tags,

		})
	else:
		form = BookmarkSaveForm()
		
	variables = RequestContext(request,
				{'form': form})
	if ajax:
		return render_to_response(
			'bookmark_save_form.htm', variables)
	else:
		return render_to_response('bookmark_save.htm', variables)
	
	
def tag_page(request, tag_name):
	tag = get_object_or_404(Tag, name=tag_name)
	bookmarks = tag.bookmarks.order_by('-id')
	variables = RequestContext(request,
		{
		'bookmarks': bookmarks,
		'tag_name': tag_name,
		'show_tags': True,
		'show_user': True
		})
	return render_to_response('tag_page.htm', variables)

def tag_cloud_page(request):
	MAX_WEIGHT = 5
	tags = Tag.objects.order_by('name')
	# Calculate tag, min and max counts.
	min_count = max_count = tags[0].bookmarks.count()
	for tag in tags:
		tag.count = tag.bookmarks.count()
		if tag.count < min_count:
			min_count = tag.count
		if max_count < tag.count:
			max_count = tag.count
	range = float(max_count - min_count)
	if range == 0.0:
		range = 1.0
	for tag in tags:
		tag.weight = int(
						MAX_WEIGHT * (tag.count - min_count)/range)
	variables = RequestContext(request,
		{'tags':tags})
	return render_to_response('tag_cloud_page.htm', variables)
	
def search_page(request):
	form = SearchForm()
	bookmarks = []
	show_results = False
	if 'query' in request.GET:
		show_results = True
		query = request.GET['query'].strip()
		if query:
			keywords = query.split()
			q = Q()
			for keyword in keywords:
				q = q & Q(title__icontains=keyword)
			form = SearchForm({'query': query})
			bookmarks = Bookmark.objects.filter(q)[:10]
	variables = RequestContext(request, {
					'form': form,
					'bookmarks': bookmarks,
					'show_results': show_results,
					'show_tags': True,
					'show_user': True
					})
	if request.GET.has_key('ajax'):
		return render_to_response('bookmark_list.htm', variables)
	else:
		return render_to_response('search.htm', variables)


def _bookmark_save(request, form):
	# Create or get a link
	link, dummy = Link.objects.get_or_create(url=form.cleaned_data['url'])
	# Create or get bookmark
	bookmark, created = Bookmark.objects.get_or_create(
	user=request.user,
	link=link)
	# Update bookmark title
	bookmark.title = form.cleaned_data['title']
	if not created:
		bookmark.tag_set.clear()
	# Create new tag list.
	tag_names = form.cleaned_data['tags'].split()
	for tag_name in tag_names:
		tag, dummy = Tag.objects.get_or_create(name=tag_name)
		bookmark.tag_set.add(tag)
	# Share on main page if requested
	if form.cleaned_data['share']:
		shared, created = SharedBookmark.objects.get_or_create(bookmark=bookmark
		)
		if created:
			shared.users_voted.add(request.user)
		shared.save()
			
	bookmark.save()
	return bookmark
	
@login_required
def bookmark_vote_page(request):
	if 'id' in request.GET:
		try:
			id=request.GET['id']
			shared_bookmark = SharedBookmark.objects.get(id=id)
			user_voted = shared_bookmark.users_voted.filter(
				username = request.user.username)
			if not user_voted:
				shared_bookmark.votes += 1
				shared_bookmark.users_voted.add(request.user)
				shared_bookmark.save()
		except SharedBookmark.DoesNotExist:
			raise Http404('Bookmark not found.')
	if 'HTTP_REFERER' in request.META:
		return HttpResponseRedirect(request.META['HTTP_REFERER'])
	return HTTPResponseRedirect('/')
	
from datetime import datetime, timedelta
def popular_page(request):
	today = datetime.today()
	thismonth = today - timedelta(30)
	shared_bookmarks = SharedBookmark.objects.filter(date__gt=thismonth)
	shared_bookmarks = shared_bookmarks.order_by('-votes')[:20]
	variables = RequestContext(request,{
		'shared_bookmarks': shared_bookmarks
	})
	return render_to_response('popular_page.htm', variables)
	
def bookmark_page(request, bookmark_id):
	shared_bookmark = get_object_or_404(SharedBookmark, id=bookmark_id)
	variables = RequestContext(request, {
		'shared_bookmark': shared_bookmark})
	return render_to_response('bookmark_page.htm', variables)
	
def friends_page(request, username):
	user = get_object_or_404(User, username=username)
	friends = [friendship.to_friend for friendship in user.friend_set.all()]
	friend_bookmarks = Bookmark.objects.filter(user__in=friends).order_by('-id')
	variables = RequestContext(request,
		{'username':username,
		'friends': friends,
		'bookmarks': friend_bookmarks[:10],
		'show_tags': True,
		'show_user': True }
		)
	return render_to_response('friends_page.htm', variables)

@login_required
def friend_add(request):
	if 'username' in request.GET:
		friend = get_object_or_404(User, username=request.GET['username'])
		friendship = Friendship(from_friend=request.user, to_friend=friend)
		friendship.save()
		return HttpResponseRedirect('/friends/%s' % request.user.username)
	else:
		raise Http404

@login_required
def friend_invite(request):
	if request.method == 'POST':
		form = FriendInviteForm(request.POST)
		if form.is_valid():
			invitation = Invitation(
				name = form.cleaned_data['name'],
				email = form.cleaned_data['email'],
				code = User.objects.make_random_password(20),
				sender=request.user)
			invitation.save()
			invitation.send()
			return HttpResponseRedirect('/friend/invite/')
	else:
		form = FriendInviteForm()
		variables = RequestContext(request,
				{'form': form})
		return render_to_response('friend_invite.htm', variables)
		
def friend_accept(request, code):
	invitation = get_object_or_404(Invitation, code__exact = code)
	request.session['invitation'] = invitation.id
	return HttpResponseRedirect('/register/')