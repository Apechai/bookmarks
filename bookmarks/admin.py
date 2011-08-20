from django.contrib import admin
from bookmarks.models import *
class LinkAdmin(admin.ModelAdmin):
	pass
admin.site.register(Link, LinkAdmin)

class BookmarkAdmin(admin.ModelAdmin):
	pass
admin.site.register(Bookmark, BookmarkAdmin)

class TagAdmin(admin.ModelAdmin):
	pass
admin.site.register(Tag, TagAdmin)

class SharedBookmarkAdmin(admin.ModelAdmin):
	pass
admin.site.register(SharedBookmark, SharedBookmarkAdmin)