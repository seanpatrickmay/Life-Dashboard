on run
	set rootPath to "/Users/seanmay/Desktop/Current Projects/Life-Dashboard"
	set pythonPath to "/Users/seanmay/Library/Caches/pypoetry/virtualenvs/life-dashboard-backend-M5vspPLW-py3.12/bin/python"
	set syncScriptPath to rootPath & "/scripts/sync_imessage.py"
	set lockDir to "/tmp/life_dashboard_imessage_sync.lock"
	set stdoutLog to "/tmp/life_dashboard_imessage_sync.log"
	set stderrLog to "/tmp/life_dashboard_imessage_sync.err.log"
	set shellCommand to "/bin/mkdir " & quoted form of lockDir & " 2>/dev/null || exit 0; " & ¬
		"trap '/bin/rmdir " & quoted form of lockDir & "' EXIT; " & ¬
		"cd " & quoted form of rootPath & "; " & ¬
		quoted form of pythonPath & " " & quoted form of syncScriptPath & " --user-id 1 --time-zone America/New_York" & ¬
		" >> " & quoted form of stdoutLog & " 2>> " & quoted form of stderrLog
	try
		do shell script shellCommand
	on error errMsg number errNum
		do shell script "/bin/echo " & quoted form of ("launcher error (" & errNum & "): " & errMsg) & " >> " & quoted form of stderrLog
	end try
end run
