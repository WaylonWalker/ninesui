Output assets/gitadd.mp4
Output assets/gitadd.gif

Require echo

Set Shell "bash"
Set FontSize 32
Set Width 1920
Set Height 1080
Set Theme 'Dracula'

Hide
Type rm delme.txt Enter
Sleep 250ms
Type "tmux kill-session -t gitadd" Enter
Sleep 250ms
Type "tmux new -s gitadd" Enter
Sleep 250ms
Type"tmux attatch -t gitadd" Enter
Type "NINES_SCREENKEY=1 ./apps/gitnine.py"
Enter
Enter
Hide
Sleep 5s
Type ":status" Sleep 500ms  Enter
Sleep 5s
Show
Alt+v
Type "touch delme.txt" Enter
Sleep 2s
Type "rm delme.txt" Enter
Sleep 1s
Type "touch delme.txt" Enter
Sleep 2s
Type "rm delme.txt" Enter
Sleep 5s

