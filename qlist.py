def build_tor_list(self):
        """Builds multiple lists of torrents to be sorted. Also adds tags to the torents.
        There are more effecient ways of doing things but I did this rather quickly.
        V2 will certainly be more performant. The reason two lists were used was so that torrents
        that are in public trackers woudln't be around as long as torrents from a private tracker.
        """
        self.total_torrents = len(self.torrent_list)
        while self.torrent_list:
            torrent = self.torrent_list.pop()
            self.tl.debug(f'---Analyzing ["{torrent["name"][0:20]}..."] {torrent["infohash_v1"]}---')
            # Need a way to tag when the tracker is blank
            if is_tracker_blank(torrent['tracker']):
                self.tl.warning(f'Torrent doesn\'t have a tracker ["{torrent["name"][0:20]}..."] hash: {torrent["hash"]}')
                self.ignored_counter += 1
                continue
            elif is_cat_ignored(torrent['category'], self.cat_whitelist.values()):
                self.tl.info(f'Ignored category: ["{torrent["name"][0:20]}..."] category:[{torrent["category"]}] hash: {torrent["hash"]}')
                self.ignored_counter += 1
                continue
            elif is_ignored_tag(self.ignored_tags.values(),torrent['tags']):
                self.tl.info(f'Ignored tag: ["{torrent["name"][0:20]}..."] tags: {torrent["tags"]} hash: {torrent["hash"]}')
                self.ignored_counter += 1
                continue
            if is_tag_blank(torrent['tags']):
                self.tl.debug(f'Tagging new torrent: ["{torrent["name"][0:20]}..."] {torrent["tracker"]}hash: {torrent["hash"]}')
                if is_protected_tracker(torrent['tracker'], self.tracker_whitelist.values()):
                    self.qbt_client.torrents_add_tags(self.tracker_protected_tag,torrent['hash'])
                elif is_not_protected_tracker(torrent['tracker'], self.tracker_whitelist.values()):
                    self.qbt_client.torrents_add_tags(self.tracker_non_protected_tag,torrent['hash'])
            if is_preme(torrent['seeding_time'], self.min_age):
                self.preme_tor_counter += 1
                self.tl.debug(f'Premature torrent: ["{torrent["name"][0:20]}..."] Seconds Seeded: [{torrent["seeding_time"]}] hash: {torrent["hash"]}')
                continue
            elif is_protected_tracker(torrent['tracker'], self.tracker_whitelist.values()):
                if is_tag_blank(torrent['tags']):
                    self.qbt_client.torrents_add_tags(self.tracker_protected_tag,torrent['hash'])
                    self.tl.debug(f'Tagging Protected torrent: ["{torrent["name"][0:20]}..."] {torrent["tracker"]}hash: {torrent["hash"]}')
                self.tracker_list.append(torrent)
            elif is_not_protected_tracker(torrent['tracker'], self.tracker_whitelist.values()):
                if is_tag_blank(torrent['tags']):
                    self.qbt_client.torrents_add_tags(self.tracker_non_protected_tag,torrent['hash'])
                    self.tl.debug(f'Tagging Non-protected torrent: ["{torrent["name"][0:20]}..."] {torrent["tracker"]}hash: {torrent["hash"]}')
                self.tracker_list.append(torrent)


def is_preme(seeding_time, minage):
    if seeding_time <= minage:
        return True

def is_cat_ignored(cat, catlist):
    if cat in catlist:
        return True

def is_tracker_blank(tracker):
    if tracker == '':
        return True

def is_protected_tracker(tracker, trackerlist):
    if tracker == '':
        return False
    if tracker.split('/')[2] in trackerlist:
        return True

def is_not_protected_tracker(tracker, trackerlist):
    if tracker == '':
        return False
    if tracker.split('/')[2] not in trackerlist:
        return True

def is_tag_blank(tag):
    if tag == '':
        return True

def is_ignored_tag(igtags, tortags):
    for igt in igtags:
        if igt in tortags:
            return True