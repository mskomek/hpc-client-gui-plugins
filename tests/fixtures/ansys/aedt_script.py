import win32com.client

oAnsysApp = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
oDesktop = oAnsysApp.GetAppDesktop()
oDesktop.RestoreWindow()
oProject = oDesktop.NewProject()
oProject.InsertDesign("HFSS", "HFSSDesign1", "Modal", "")
