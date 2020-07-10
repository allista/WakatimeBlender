**WakatimeBlender** is a simple plugin for the [Blender](https://www.blender.org/) 3D graphics software that sends time-tracking statistics to the [Wakatime](https://wakatime.com) online service using official wakatime client.

### Installation

To install the plugin you need, in fact, only the [WakaTime.py](https://github.com/allista/WakatimeBlender/raw/master/WakaTime.py) file.
Download it somewhere, open the Blender, go to *File->User Preferences->Add-ons->Install from file*, then check the tick-box near the plugin name in the list to enable it. Finally, push *Save User Settings*.

![Installation](http://i.imgur.com/3ZtsKpb.png)

After that a dialog prompting to enter the WakaTime API key may appear. Enter your key here and push "OK". If the key is incorrect and an attempt to send statistics fails the dialog is shown again.

![Setup API Key dialog](http://i.imgur.com/2VDvtJ9.png)

If for some reason you wish to change the key, press Space to summon the floating menu, then start type "waka" until the "Enter WakaTime API Key" action is shown. Select that action to summon the dialog again.

![Setup API Key](http://i.imgur.com/if3PLTC.png)

When setup is finished, the plugin should start sending the time you've spent on the currently loaded .blend file automatically in the background. **Note**, that unless you save a newly created file no stats are gathered, because Wakatime needs a filepath.

### Configuration
WakaTime will try to detect the projects name, e.g. from the git-repo.
If one does not work with git, the project's name would be "Unknown Project" within WakaTime.
<br/>
So this Add-On can try to "guess" the projects name from the current blend-filename or from the project-folder.

To fine-tune the project's name, there are some options available under *Preferences -> Add-ons -> WakaTime*.<br/>
(This is also the place where to enable the add-on.)

![Configuration](https://i.imgur.com/Sw8F9JN.png)

The first check-box decides, whether to **always** use the guessed name from this AddOn, effectively overwriting WakaTimes discovered name (i.e. the git-repo).

The next check-box decides, on what to base the WakaTime-project-name:
* if not checked: use the filename (without the *.blend*-extensions), or
* if checked: use the directory-name (of the blend-file).

With the project-name extracted, further processing takes place:
1. If there are specific (default: numbers, underscores and dots) **trailing** characters, those will be removed too.
2. Optional: add a prefix to the project's title.
3. Optional: add a postfix to the project's title.

#### Examples
1. To give the project-name a ".blend"-extension, add ".blend" in the postfix-text-field.
2. To only remove trailing numbers (e.g. versions), enter "1234567890" in the trailing character-text-field and press enter.
3. To remove numbers, underscores and dots, enter "1234567890.\_" in the trailing character-text-field and press enter. (This is the default.)
4. To turn "captain_afterburner.blend" into the project-name "\[blender\] captain_afterburner", set the prefix to "\[blender\] ", the postfix to "" (nothing).
5. To turn "captain_afterburner_05.blend" into the project-name "\[blender\] captain_afterburner", apply steps #3 and #4 together.
6. If you want to use the directory's name, check "Use folder-name as project-name". All steps from #1 to #5 can still be used to adjust the name.
7. To prevent any adjusting of the projects-name, remove all the characters from all three text-fields and press enter.
