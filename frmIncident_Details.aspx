<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmIncident_Details.aspx.cs"
    Inherits="Fleet_Personnel_frmIncident_Details" MaintainScrollPositionOnPostback="true"%>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>Incident Information</title>
    <link href="../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/CommonModal.js"></script>
    
    <link href="../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />

    <script type="text/javascript">
        window.onload = function() {
         
         //   if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value != "")
            {
                if (document.getElementById('<%=ddlPerson_Injured.ClientID%>').value == "Y") {
                    if (document.getElementById('<%=ddlThird_Party.ClientID%>').value == "10" || document.getElementById('<%=ddlThird_Party.ClientID%>').value == "30"
                || document.getElementById('<%=ddlThird_Party.ClientID%>').value == "308" || document.getElementById('<%=ddlThird_Party.ClientID%>').value == "2")///Operator
                    {
                        document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'none';
                    }
                    else {
                        document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'inline';
                    }
                }
                else if (document.getElementById('<%=ddlPerson_Injured.ClientID%>').value == "N") {
                    document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'none';
                    ClearPersonInjuredData();
                }
            }
            //            if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value == "") 
            //            {           
            //           
            //                   if (document.getElementById('<%=ddlPerson_Injured.ClientID%>').value == "Y") 
            //                  {
            //                  
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').value="";
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').className = "textbox";                 
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').detachEvent("onkeydown", RejectInput);

            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').value="";
            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').className = "textbox_right";                 
            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').detachEvent("onkeydown", RejectInput);
            //      
            //                        document.getElementById('<%=tbRank_Id_Hidden.ClientID%>').value="";
            //                        document.getElementById('<%=tbRank_Name.ClientID%>').value="";
            //                                                
            //                        document.getElementById('<%=ddlThird_Party.ClientID%>').value  = "N";                        
            //                        
            //                        document.getElementById('<%=ibtnRank.ClientID %>').style.display ='inline';                        
            //                        document.getElementById('<%=ddlThird_Party.ClientID %>').disabled=false;   
            //                     
            //                        document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value="";       
            //                        document.getElementById('<%=tbContractor_Name.ClientID%>').value = "";    
            //                       
            //                                            
            //                  }  
            //                  else
            //                  {               
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').value="";
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').className = "textbox_readonly";                 
            //                        document.getElementById('<%=tbEmp_Name.ClientID%>').attachEvent("onkeydown",RejectInput);  

            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').value="";
            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').className = "textbox_right_readonly";                 
            //                        document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').attachEvent("onkeydown",RejectInput);  
            //                        
            //                        
            //                        document.getElementById('<%=tbRank_Id_Hidden.ClientID%>').value = "";
            //                        document.getElementById('<%=tbRank_Name.ClientID%>').value = "";
            //                        document.getElementById('<%=ddlThird_Party.ClientID%>').value = "N";              
            //                  
            //                        document.getElementById('<%=ibtnRank.ClientID %>').style.display ='none';                        
            //                        document.getElementById('<%=ddlThird_Party.ClientID %>').disabled=true;
            //                        
            //                        document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value="";       
            //                        document.getElementById('<%=tbContractor_Name.ClientID%>').value = "";  
            //                        
            //                        document.getElementById('<%=ibtnContractor.ClientID %>').style.display ='none';
            //                  }
            //                  
            //                  if (document.getElementById('<%=ddlThird_Party.ClientID%>').value == "Y" && document.getElementById('<%=ddlThird_Party.ClientID %>').disabled == false)  
            //                  {
            //                      document.getElementById('<%=ibtnContractor.ClientID %>').style.display ='inline';  
            //                  }  
            //                  else
            //                  {
            //                   
            //                    document.getElementById('<%=ibtnContractor.ClientID %>').style.display ='none';
            //                  } 
            //                  
            //                    
            //           }

        }

        function Open_DownloadTemplate(HR_DownloadTemplate) {
            SetPostbackFlag('TEMPLATE_DOWNLOAD');
            window.open(HR_DownloadTemplate, '_blank', 'left=0,top=0,height=2000,width=2000, resizable=yes, status=yes');
            return false;
        }
        function Check_File_Selected(strVal) {
            if (strVal == "REC") {
                if (document.getElementById('<%=fupd_ExcelSheet.ClientID %>').value == "") {
                    alert("Select the File first");
                    return false;
                }
            }

        }
        function getExtension(filename) {
            var parts = filename.split('.');
            return parts[parts.length - 1];
        }

        function chk_Image_Extention(filename) {
            var ext = getExtension(filename);
            switch (ext.toLowerCase()) {
                case 'jpg':
                case 'jpeg':
                case 'bmp':
                case 'gif':
                case 'tiff':
                case 'png':

                    return true;
            }
            return false;
        }

        function Chk_Image_Selected() {

            var grid = document.getElementById("<%= grdInc_Images.ClientID %>");
            var inputs = grid.getElementsByTagName("input");
            var fileUpload;
            var arr = new Array(inputs.length);

            for (var i = 0; i < inputs.length; i++) {
                if (inputs[i].type == "file") {
                    fileUpload = inputs[i];


                    if (fileUpload.value == "") {
                        arr[i] = "N";
                    }
                    else {
                        arr[i] = "Y";
                    }



                }
            }
            var isImageSelected = "N";
            for (var i = 0; i < inputs.length; i++) {

                if (arr[i] == "Y") {
                    isImageSelected = "Y";
                }
            }

            return isImageSelected;

        }
        function Chk_Inc_Ext_Duplicate_File(obj) {
            if (document.getElementById('<%=tbPostbackFlag_Hidden.ClientID %>').value == "IMG_UPLOAD") {
                var grid = document.getElementById("<%= grdInc_Images.ClientID %>");
                var inputs = grid.getElementsByTagName("input");
                var fileUpload;
                var strRowNo = obj.value;
                var Cur_Row_Val = obj.id;
                var Row_To_Chk_Val = "";


                for (var i = 0; i < inputs.length; i++) {
                    if (inputs[i].type == "file") {
                        fileUpload = inputs[i];
                        Row_To_Chk_Val = fileUpload.id;
                        var isToDelete = "N";


                        if (fileUpload.value != "" && strRowNo != "") {
                            var strImage_Extention = chk_Image_Extention(fileUpload.value);

                            if (strImage_Extention == false) {
                                alert("Invalid File Type !!!");
                                isToDelete = "Y";
                            }
                        }
                        if (Cur_Row_Val != Row_To_Chk_Val) {

                            if (fileUpload.value != "" && strRowNo != "") {
                                if (fileUpload.value == strRowNo) {
                                    //Check the Row to delete     
                                    alert("Duplicate file found ,Select another");
                                    isToDelete = "Y";

                                    // obj.focus(); 

                                }
                            }
                        }

                        if (isToDelete == "Y") {
                            obj.select();
                            n = obj.createTextRange();
                            n.execCommand('delete');
                        }
                    }
                }
            }
        }


        function Clear_Image_Path(obj) {

            var grid = document.getElementById("<%= grdInc_Images.ClientID %>");
            var inputs = grid.getElementsByTagName("input");
            var fileUpload;
            var strRowNo = obj.id.toString().split("_")[3]; //get row number


            strRowNo = obj.id.replace("Button1", "fupd_Inc_Images");

            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID %>').value == "CLEAR_FILE_UPLOAD";


            for (var i = 0; i < inputs.length; i++) {
                if (inputs[i].type == "file") {
                    fileUpload = inputs[i];
                    if (fileUpload.id == strRowNo) {
                        //Check the Row to delete                                     
                        fileUpload.select();
                        n = fileUpload.createTextRange();
                        n.execCommand('delete');
                        // fileUpload.focus(); 

                    }
                }
            }




        }
        function validate(strFlag) {
            var msg = "";

            var strServerDt = '<%= Session["ServerDt"].ToString() %>';

            /// Set a value to indicate the control/event that causes a postback.
            SetPostbackFlag(strFlag);

             
            if (strFlag == "DELETE_CANCEL")
            {
                document.getElementById("divbgPopup").style.visibility = "hidden";
                return false;
            }

            if (strFlag == "DELETE_OK") {

                if (document.getElementById('<%=tbDeleted_Remarks.ClientID%>').value == "") {

                    msg += "- Reason for delete record must tbe entered<br><br>";
                    document.getElementById('<%=tbDeleted_Remarks.ClientID%>').focus();
                }
                else {

                    document.getElementById('<%=tbDeleted_Remarks.ClientID%>').value =alltrim(document.getElementById('<%=tbDeleted_Remarks.ClientID%>').value);
                    if (document.getElementById('<%=tbDeleted_Remarks.ClientID%>').value.length < 10) {
                         msg += "- Reason for delete lengh must be at least 10 characters<br><br>";
                         document.getElementById('<%=tbDeleted_Remarks.ClientID%>').focus();
                    }

                }


                if (msg == "") {
                    return true;
                }
            }


            if (strFlag == "DELETE") {

                if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'You are currently in Delete mode. A new record cannot be deleted in this mode.');
                    return false;
                }
                
                if (document.getElementById("divbgPopup").style.visibility == "hidden") {
                    var res = confirm("Clicking Delete will remove all uploaded photos,root cause and actions of the selected incident ? \nContinue with delete ?");
                    if (res == true) {

                        document.getElementById("divbgPopup").style.visibility = "visible";
                        document.getElementById('<%=tbDeleted_Remarks.ClientID%>').focus();
                        return false;
                    }
                    else {

                        return false;
                    }
                }
                else {

                    document.getElementById('<%=tbDeleted_Remarks.ClientID%>').focus();
                      return false;
                }

            }

            if (strFlag == "ADD") {
                /// Blocking ADD button when an existing record is selected.
                if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value != "") {
                    ShowMessage(400, 75, 'You are currently in Update mode. A new record cannot be added in this mode.');
                    return false;
                }

                if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "" && document.getElementById('<%=tbUnit_Name.ClientID%>').value == "") {
                    document.getElementById('<%=tbRig.ClientID%>').focus();
                    msg += "- Rig must be selected / Unit Name must be entered <br><br>";
                }
                else if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value != "" && document.getElementById('<%=tbUnit_Name.ClientID%>').value != "") {
                    document.getElementById('<%=tbRig.ClientID%>').focus();
                    msg += "- Rig / Unit Name both cannot selected <br><br>";
                }


                if (document.getElementById('<%=tbIncident_Date.ClientID%>').value == "") {
                    document.getElementById('<%=tbIncident_Date.ClientID%>').focus();
                    msg += "- Incident Date must be entered <br><br>";
                }
                else {

                    if (document.getElementById('<%=tbIncident_Time.ClientID%>').value == "") {
                        msg += "- Incident Time must be entered<br><br>";
                        document.getElementById('<%=tbIncident_Time.ClientID%>').focus();
                    }
                    if (checkDate(document.getElementById('<%=tbIncident_Date.ClientID%>').value)) {

                        if (compareDates(document.getElementById('<%=tbIncident_Date.ClientID%>').value, 'dd/MM/yyyy', strServerDt, 'dd/MM/yyyy') != 0) {
                            msg += "- Incident date must be less than or equal to current date<br><br>";
                            document.getElementById('<%=tbIncident_Date.ClientID%>').focus();
                        }

                    }
                    else {
                        msg += "- Invalid Incident Date<br><br>";
                        document.getElementById('<%=tbIncident_Date.ClientID%>').focus();
                    }
                }

                if (document.getElementById('<%=ddlIncident_Party.ClientID%>').value == "") {
                    msg += "- Incident belongs to must be selected<br><br>";
                    document.getElementById('<%=ddlIncident_Party.ClientID%>').focus();
                }
                
                //////tbIncident_Reported_Dt
                if (document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').value == "") {
                    document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').focus();
                    msg += "- Incident Reported Date must be entered <br><br>";

                }
                else {

                    if (document.getElementById('<%=tbIncident_Reported_Time.ClientID%>').value == "") {
                        msg += "- Incident Reported Time must be entered<br><br>";
                        document.getElementById('<%=tbIncident_Reported_Time.ClientID%>').focus();
                    }
                    if (checkDate(document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').value)) {
                        //                        if (compareDates(document.getElementById('<%=tbIncident_Date.ClientID%>').value, 'dd/MM/yyyy', document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').value, 'dd/MM/yyyy') == 1)
                        //                         {
                        //                                msg += "- Incident Reported Date must be greater than Incident date<br><br>";
                        //                                document.getElementById('<%=tbIncident_Date.ClientID%>').focus();
                        //                         }   

                        if (compareDates(document.getElementById('<%=tbIncident_Date.ClientID%>').value + ' ' + document.getElementById('<%=tbIncident_Time.ClientID%>').value, 'dd/MM/yyyy HH:mm', document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').value + ' ' + document.getElementById('<%=tbIncident_Reported_Time.ClientID%>').value, 'dd/MM/yyyy HH:mm') == 0) {
                        }
                        else {
                            msg += "- Incident Reported Date must be greater than Incident date<br><br>";
                            document.getElementById('<%=tbIncident_Reported_Dt.ClientID%>').focus();
                        }

                    }
                    else {
                        msg += "- Invalid Incident Date<br><br>";
                        document.getElementById('<%=tbIncident_Date.ClientID%>').focus();
                    }
                }



                if (document.getElementById('<%=tbIncident_Type_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbIncident_Type.ClientID%>').focus();
                    msg += "- Nature of Accident/Incident  must be selected <br><br>";
                }


               
                if (document.getElementById('<%=tbImmediate_Incident_Cause_Id_1_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbImmediate_Cause_1.ClientID%>').focus();
                    msg += "- Immediate Cause must be selected <br><br>";
                }

                if (document.getElementById('<%=tbRig_Operation_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbRig_Operation_Name.ClientID%>').focus();
                    msg += "- Rig Operation must be selected <br><br>";
                }

                if (document.getElementById('<%=tbWork_Location_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbWork_Location_Name.ClientID%>').focus();
                    msg += "- Work Location must be selected <br><br>";
                }
                if (document.getElementById('<%=tbContact_Expo_Type_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbContact_Expo_Type_Name.ClientID%>').focus();
                    msg += "- Contact / Expo Type must be selected <br><br>";
                }
                if (document.getElementById('<%=tbFinancial_Loss_Amt.ClientID%>').value != "") {
                    if (parseInt(document.getElementById('<%=tbFinancial_Loss_Amt.ClientID%>').value) > 0) {
                        if (document.getElementById('<%=tbFinancial_Loss_Currency_Id_Hidden.ClientID%>').value == "") {
                            msg += "- Currency must be selected.<br><br>";
                        }
                    } 
                }



            }
            else /// UPDATE
            {
                /// Blocking ADD button when an existing record is selected.
                if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'Select record to Update.');
                    return false;
                }
                //                else
                //                {
                //                    ShowMessage(400, 75, 'Updation is not allowed.');
                //                    return false;
                //                }

            }

            ///////////////Common Validation

            document.getElementById('<%=tbIncident_Descr.ClientID%>').value = alltrim(document.getElementById('<%=tbIncident_Descr.ClientID%>').value)
            if (document.getElementById('<%=tbIncident_Descr.ClientID%>').value == "") {
                document.getElementById('<%=tbIncident_Descr.ClientID%>').focus();
                    msg += "- Description must be entered <br><br>";
                }

            ///if Person_Injured="Y" then Following fields are compulsary
            if (document.getElementById('<%=ddlPerson_Injured.ClientID%>').value == "Y") {


                if (document.getElementById('<%=ddlThird_Party.ClientID%>').value == "0" || document.getElementById('<%=ddlThird_Party.ClientID%>').value == "1") {
                    if (document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value == "") {
                        document.getElementById('<%=tbContractor_Name.ClientID%>').focus();
                        msg += "- Contractor must be selected <br><br>";
                    }
                }


                document.getElementById('<%=tbEmp_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbEmp_Name.ClientID%>').value)
                if (document.getElementById('<%=tbEmp_Name.ClientID%>').value == "") {
                    document.getElementById('<%=tbEmp_Name.ClientID%>').focus();
                    msg += "- Name of Person must be entered <br><br>";
                }


                if (document.getElementById('<%=tbRank_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbRank_Name.ClientID%>').focus();
                    msg += "- Injured Person's designation must be selected <br><br>";
                }

                if (document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').value == "") {
                    document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').focus();
                    msg += "- Total Rig/Field Exp in months must be entered <br><br>";
                }

                if (document.getElementById('<%=tbPart_Of_Body_Id_Hidden_1.ClientID%>').value == ""
                    && document.getElementById('<%=tbPart_Of_Body_Id_Hidden_2.ClientID%>').value == ""
                    && document.getElementById('<%=tbPart_Of_Body_Id_Hidden_3.ClientID%>').value == ""
                    && document.getElementById('<%=tbPart_Of_Body_Id_Hidden_4.ClientID%>').value == "") {
                    document.getElementById('<%=tbPart_Of_Body_Name_1.ClientID%>').focus();
                    msg += "- Atleast One Part Of Body must be Injured. <br><br>";
                }


            }

            
            //sumit dms path
            ///If Resume File Name is Entered, not entered  DMS_Path_Resume 
            document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value = alltrim(document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value);
            document.getElementById('<%=tbResume_File_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbResume_File_Name.ClientID%>').value);
            document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value);

            if (document.getElementById('<%=tbResume_File_Name.ClientID%>').value != "") {
                if (document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value == "") {
                    document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').focus();
                    msg += "- Resume on DMS must be entered <br><br>";
                }
            }
            if (document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value != "") {
                if (document.getElementById('<%=tbResume_File_Name.ClientID%>').value == "") {
                    document.getElementById('<%=tbResume_File_Name.ClientID%>').focus();
                    msg += "- File Name must be entered <br><br>";
                }
            }

            Check_Slash_strEnd(document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>'));
            Check_Slash_strEnd(document.getElementById('<%=tbDMS_Folder_Name.ClientID%>'));
            if (msg == "") {

                if (strFlag == "ADD") {
                    var isImageSelected = Chk_Image_Selected();
                    if (isImageSelected == "N") {
                        var res = confirm("There are no pictures selected for uploading.  Continue with Add?")

                        if (res == false) {
                            return false;

                        }
                    }
                }
            }

            if (Check_FolderPath(document.getElementById('<%=tbDMS_Folder_Name.ClientID%>')) == false) {
                return false;
            }
            if (Check_Folder(document.getElementById('<%=tbResume_File_Name.ClientID%>')) == false) {
                return false;
            }
            if (msg == "") {
                return true;
            } else {
                ShowErrorWin1(msg);
                return false;
            }
        }
        function Show_Main_Data() {
            SetPostbackFlag("SEARCH");
            Open_Search_Window('INCIDENT_DETAILS', document.forms[0].name, 'tbIncident_Id_Hidden', 'tbRig_Incident_No', '', '%', 'Y', 'Y', 'N');
            return;
        }
        function Disp_Contractor() {

            if (document.getElementById('<%=ddlThird_Party.ClientID%>').value == "0" ||document.getElementById('<%=ddlThird_Party.ClientID%>').value == "1") {
                document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'inline';
            }
            else {

                document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value = "";
                document.getElementById('<%=tbContractor_Name.ClientID%>').value = "";
                document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'none';
            }
        }


        function Disp_Person_Injured() {

            if (document.getElementById('<%=ddlPerson_Injured.ClientID%>').value == "Y") {

                document.getElementById('<%=tbEmp_Name.ClientID%>').value = "";
                document.getElementById('<%=tbEmp_Name.ClientID%>').className = "textbox";
                document.getElementById('<%=tbEmp_Name.ClientID%>').detachEvent("onkeydown", RejectInput);

                document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').value = "";
                document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').className = "textbox_right";
                document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').detachEvent("onkeydown", RejectInput);


                //Previous code enable the dropdown box of injured body
                ShowHideBodyParts('Y');


                document.getElementById('<%=tbRank_Id_Hidden.ClientID%>').value = "";
                document.getElementById('<%=tbRank_Name.ClientID%>').value = "";

                document.getElementById('<%=ddlThird_Party.ClientID%>').value = "0";

                document.getElementById('<%=ibtnRank.ClientID %>').style.display = 'inline';
                document.getElementById('<%=ddlThird_Party.ClientID %>').disabled = false;

                document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value = "";
                document.getElementById('<%=tbContractor_Name.ClientID%>').value = "";


            }
            else {
                var strClear = "Y";

                if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value != "") {


                    var res = confirm("All other values related to Person Injured will be removed.  Do you want to proceed ?");

                    if (res == true) {
                        strClear = "Y";
                        document.getElementById('<%=ddlPerson_Injured.ClientID%>').value = "N";
                    }
                    else {
                        strClear = "N";
                        document.getElementById('<%=ddlPerson_Injured.ClientID%>').value = "Y";

                    }
                }

                if (strClear == "Y") {
                    ClearPersonInjuredData();
                }
            }
        }
        function ClearPersonInjuredData() {
            document.getElementById('<%=tbEmp_Name.ClientID%>').value = "";
            document.getElementById('<%=tbEmp_Name.ClientID%>').className = "textbox_readonly";
            document.getElementById('<%=tbEmp_Name.ClientID%>').attachEvent("onkeydown", RejectInput);

            document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').value = "";
            document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').className = "textbox_right_readonly";
            document.getElementById('<%=tbTotal_Rig_Exp_Months.ClientID%>').attachEvent("onkeydown", RejectInput);


            document.getElementById('<%=tbRank_Id_Hidden.ClientID%>').value = "";
            document.getElementById('<%=tbRank_Name.ClientID%>').value = "";
            document.getElementById('<%=ddlThird_Party.ClientID%>').value = "0";

            document.getElementById('<%=ibtnRank.ClientID %>').style.display = 'none';
            document.getElementById('<%=ddlThird_Party.ClientID %>').disabled = true;

            //Previous code was disable the dropdown box of injured body and remove that dropdown
            ShowHideBodyParts('N');

            document.getElementById('<%=tbPart_Of_Body_Name_1.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Name_2.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Name_3.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Name_4.ClientID %>').value = "";


            document.getElementById('<%=tbPart_Of_Body_Id_Hidden_1.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Id_Hidden_2.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Id_Hidden_3.ClientID %>').value = "";
            document.getElementById('<%=tbPart_Of_Body_Id_Hidden_4.ClientID %>').value = "";




            document.getElementById('<%=tbContractor_Id_Hidden.ClientID%>').value = "";
            document.getElementById('<%=tbContractor_Name.ClientID%>').value = "";

            document.getElementById('<%=ibtnContractor.ClientID %>').style.display = 'none';
        }
        function ShowHideBodyParts(status) {

            if (status == 'Y') {
                document.getElementById('<%=ibtnPart_Of_Body_Name_1.ClientID %>').style.display = 'inline';
                document.getElementById('<%=ibtnPart_Of_Body_Name_2.ClientID %>').style.display = 'inline';
                document.getElementById('<%=ibtnPart_Of_Body_Name_3.ClientID %>').style.display = 'inline';
                document.getElementById('<%=ibtnPart_Of_Body_Name_4.ClientID %>').style.display = 'inline';
                //alert('1');

                document.getElementById('imgPart_Of_Body_Name_1').style.display = 'inline';
                document.getElementById('imgPart_Of_Body_Name_2').style.display = 'inline';
                document.getElementById('imgPart_Of_Body_Name_3').style.display = 'inline';
                document.getElementById('imgPart_Of_Body_Name_4').style.display = 'inline';
            } else {
                document.getElementById('<%=ibtnPart_Of_Body_Name_1.ClientID %>').style.display = 'none';
                document.getElementById('<%=ibtnPart_Of_Body_Name_2.ClientID %>').style.display = 'none';
                document.getElementById('<%=ibtnPart_Of_Body_Name_3.ClientID %>').style.display = 'none';
                document.getElementById('<%=ibtnPart_Of_Body_Name_4.ClientID %>').style.display = 'none';

                document.getElementById('imgPart_Of_Body_Name_1').style.display = 'none';
                document.getElementById('imgPart_Of_Body_Name_2').style.display = 'none';
                document.getElementById('imgPart_Of_Body_Name_3').style.display = 'none';
                document.getElementById('imgPart_Of_Body_Name_4').style.display = 'none';
            }
        }
        function ShowCountry() {
            SetPostbackFlag("COUNTRY");
            Open_Search_Window('COUNTRY', document.forms[0].name, 'tbCountry_Id_Hidden', 'tbCountry_Name', '', '', 'N', 'Y', 'N');
            return;
        }

        function Show_Rig() {
            SetPostbackFlag("RIG");
            //var strFilterString = " Own_Ship_Co_Id In (1, 2) And isnull(Vessel_To, Getdate()) > '2008-03-31' ";            
            Open_Search_Window('RIG', document.forms[0].name, 'tbRig_Id_Hidden', 'tbRig', '', '%', 'Y', 'Y', 'N');
            return;
        }

        function Show_Currency() {
            SetPostbackFlag("CURRENCY");
            var strSearchString = "";
            Open_Search_Window('CURRENCY', document.forms[0].name, 'tbFinancial_Loss_Currency_Id_Hidden', 'tbFinancial_Loss_Currency', '', strSearchString, 'N', 'Y', 'N');
            return;
        }


        function Show_Immediate_Incident_Cause(objVal) {
            if (objVal == "1") {
                SetPostbackFlag("INCIDENT_IMMEDIATE_CAUSE_1");
                var strFilterString = " Incident_Cause_Category In ('I','B')";
                Open_Search_Window('INCIDENT_CAUSE', document.forms[0].name, 'tbImmediate_Incident_Cause_Id_1_Hidden', 'tbImmediate_Cause_1', strFilterString, '%', 'N', 'Y', 'N');
                return;
            }
            else if (objVal == "2") {
                SetPostbackFlag("INCIDENT_IMMEDIATE_CAUSE_2");
                var strFilterString = " Incident_Cause_Category In ('I','B')";
                Open_Search_Window('INCIDENT_CAUSE', document.forms[0].name, 'tbImmediate_Incident_Cause_Id_2_Hidden', 'tbImmediate_Cause_2', strFilterString, '%', 'N', 'Y', 'N');
                return;
            }
        }


        function Show_Incident_Type() {
            SetPostbackFlag("INCIDENT_TYPE")
            Open_Search_Window('INCIDENT_TYPE', document.forms[0].name, 'tbIncident_Type_Id_Hidden', 'tbIncident_Type', '', '%', 'N', 'N', 'N');
            return;
        }
        function Show_Operator() {
            SetPostbackFlag("MST_OPERATOR");
            Open_Search_Window('MST_OPERATOR', document.forms[0].name, 'tbOperator_Id_Hidden', 'tbOperator_Name', '', '%', 'N', 'Y', 'N');
            return;
        }
        function Show_Contractor() {
            if (document.getElementById('<%=ddlThird_Party.ClientID%>').value == "0" ||
                document.getElementById('<%=ddlThird_Party.ClientID%>').value == "1"
                ) {}
            else
            {
                alert("TP Contractor Name cannot be selected.");
                return false;
            }
            SetPostbackFlag("MST_CONTRACTOR");
            Open_Search_Window('MST_CONTRACTOR', document.forms[0].name, 'tbContractor_Id_Hidden', 'tbContractor_Name', '', '%', 'N', 'Y', 'N');
            return;
        }
        function ShowFsEmployee() {
            SetPostbackFlag("FSEMPLOYEE");
            Open_Search_Window('FS_EMPLOYEE', document.forms[0].name, 'tbFs_Emp_Id_Hidden', 'tbReported_By', '', '', 'Y', 'Y', 'N');
            return;
        }

        function ShowRank(objVal) {

            if (objVal == "Injure") {
                SetPostbackFlag("X_RANK_INJURE");
                Open_Search_Window('RANK', document.forms[0].name, 'tbRank_Id_Hidden', 'tbRank_Name', '', '%', 'N', 'Y', 'N');
                return false;
            }
            else {
                SetPostbackFlag("X_RANK_RPTED");
                Open_Search_Window('RANK', document.forms[0].name, 'tbRptd_By_Rank_Id_Hidden', 'tbRptd_By_Rank_Name', '', '%', 'N', 'Y', 'N');
                return false;
            }


        }


        function Show_Rig_Operation() {
            SetPostbackFlag("MST_RIG_OPERATION");
            Open_Search_Window('MST_RIG_OPERATION', document.forms[0].name, 'tbRig_Operation_Id_Hidden', 'tbRig_Operation_Name', '', '%', 'N', 'Y', 'N');

            return;
        }

        function Show_Contact_Exposure_Type() {
            SetPostbackFlag("MST_CONTACT_EXPOSURE_TYPE");
            Open_Search_Window('MST_CONTACT_EXPOSURE_TYPE', document.forms[0].name, 'tbContact_Expo_Type_Id_Hidden', 'tbContact_Expo_Type_Name', '', '%', 'N', 'Y', 'N');

            return;
        }
   

        function Show_Work_Location() {
            SetPostbackFlag("WORK_LOCATION");
            var strSearchString = "%";
            Open_Search_Window('WORK_LOCATION', document.forms[0].name, 'tbWork_Location_Id_Hidden', 'tbWork_Location_Name', '', strSearchString, 'N', 'N', 'N');
            return;
        }

        //Added by sumit
        function Show_Injured_Parts_1() {
            SetPostbackFlag("MST_PARTS_OF_BODY1")
            Open_Search_Window('MST_PARTS_OF_BODY', document.forms[0].name, 'tbPart_Of_Body_Id_Hidden_1', 'tbPart_Of_Body_Name_1', '', '%', 'N', 'N', 'N');
            return;
        }
        function Show_Injured_Parts_2() {
            SetPostbackFlag("MST_PARTS_OF_BODY2")
            Open_Search_Window('MST_PARTS_OF_BODY', document.forms[0].name, 'tbPart_Of_Body_Id_Hidden_2', 'tbPart_Of_Body_Name_2', '', '%', 'N', 'N', 'N');
            return;
        }
        function Show_Injured_Parts_3() {
            SetPostbackFlag("MST_PARTS_OF_BODY3")
            Open_Search_Window('MST_PARTS_OF_BODY', document.forms[0].name, 'tbPart_Of_Body_Id_Hidden_3', 'tbPart_Of_Body_Name_3', '', '%', 'N', 'N', 'N');
            return;
        }
        function Show_Injured_Parts_4() {
            SetPostbackFlag("MST_PARTS_OF_BODY4")
            Open_Search_Window('MST_PARTS_OF_BODY', document.forms[0].name, 'tbPart_Of_Body_Id_Hidden_4', 'tbPart_Of_Body_Name_4', '', '%', 'N', 'N', 'N');
            return;
        }


        function CheckMaxLen(obj, length) {
            checkTextAreaMaxLength(obj, event, length);
        }


        function Validate_Financial_Loss_Amt() {

            SetPostbackFlag("FINANCIAL_LOSS_AMT");
            var valid_input = isCharValid(document.getElementById('<%=tbFinancial_Loss_Amt.ClientID %>').value, 'N');
            var strText = document.getElementById('<%=tbFinancial_Loss_Amt.ClientID %>').value;
            var len = strText.length;

            if (!valid_input) {
                document.getElementById('<%=tbFinancial_Loss_Amt.ClientID %>').value = document.getElementById('<%=tbFinancial_Loss_Amt.ClientID %>').value.substr(0, len - 1);
                return;
            }
        }


        function SetVal() {
            if (document.getElementById('<%=tbPostbackFlag_Hidden.ClientID %>').value == "X_INCIDENT_TYPE") {
                document.getElementById('<%=tbIncident_Type.ClientID %>').value = HtmlDecode(document.getElementById('<%=tbIncident_Type.ClientID %>').value)
            }
        }

        function Check_Input(obj) {
            var strText = obj.value;
            var len = strText.length;

            if (!isCharValid(obj.value, 'AS')) {
                obj.value = obj.value.substr(0, len - 1);
                return;
            }

            if (len == 1 && strText == " ") {
                obj.value = obj.value.substr(0, len - 1);
                return;
            }
        }

        function Show_Wkg_Incident_Dtl() {
            SetPostbackFlag("WKG_INCIDENT_DTL");
            var strFilterString = " Upload_Status = 'U'";
            Open_Search_Window('WKG_INCIDENT_DTL', document.forms[0].name, 'tbWkg_Incident_Dtl_Id_Hidden', 'tbVessel', strFilterString, '%', 'Y', 'Y', 'N');
            return;
        }

        function Validate_Print() {
            if (document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value == "") {
                alert("Incident must be selected");
                return false;
            }

            return true;
        }


        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }

        function Validate_Numeric(obj) {
            var valid_input = isCharValid(obj.value, 'N');
            var strText = obj.value;
            var len = strText.length;

            if (!valid_input) {
                obj.value = obj.value.substr(0, len - 1);
                return;
            }
        }

        function Validate_Decimal(obj) {
            var valid_input = isCharValid(obj.value, 'NO');
            var strText = obj.value;
            var len = strText.length;

            if (!valid_input) {
                obj.value = obj.value.substr(0, len - 1);
                return;
            }
        }

        /*
        function fncIncident_Date(obj) {
        var flgResult = CheckDateOnBlur(obj);
        SetPostbackFlag("INCIDENT_DATE_CHANGE")
        if (flgResult != false && document.getElementById('<%=tbIncident_Id_Hidden.ClientID%>').value == "" && obj.value != "") {
        __doPostBack();
        return true;
        } else {
        return false;
        }
        return true;
        }  
        */

        function Image_Window(URL) {
            var New_window = window.open(URL, '_blank', 'left=0,top=0,height=500,width=500, resizable=yes, status=yes');
        }

        function Set_DMS_Path() {

            /// Reading value of strDebugMoveYN declared in code behind.
            var strDebugModeYN = "<%=strDebugModeYN%>";

            if (strDebugModeYN == "Y") {
                document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value = "http://essdmsmum/espl/ShippingPortLogistics/IT/System/";
            }
            else {
                //Online Path
                document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value = "http://Essdmsmum/espl/Oilfieldservices/QHSE Documents/";
            }
        }
        function Check_FolderPath(obj) {
            //document.getElementById('<%=tbDMS_Folder_Name.ClientID%>');
            var str = obj.value;
            var n = str.lastIndexOf("*"); //Check that File not contains the * 
            if (obj.value != "") {
                if (n != "-1") {
                    alert("Folder name should not contain *.")
                    return false;
                }
            }
        }
        function Check_Folder(obj) {

            document.getElementById('<%=tbResume_File_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbResume_File_Name.ClientID%>').value);


            var str = obj.value;
            var chkStar = str.indexOf("*");

            if (chkStar != "-1") {
                alert("File should not contain *.")
                return false;
            }
            var n = str.lastIndexOf("."); //Check that File contains the DOT 
            if (obj.value != "") {
                if (n == "-1") {
                    alert("File Extention must be entered.")
                    return false;
                }
            }

            var n = str.lastIndexOf("/"); //Check that File not contains the / 
            if (obj.value != "") {
                if (n != "-1") {
                    alert("File should not contain /.")
                    return false;
                }
            }

            var n = str.lastIndexOf("*"); //Check that File not contains the / 
            if (obj.value != "") {
                if (n != "-1") {
                    alert("File should not contain *.")
                    return false;
                }
            }


            /***** To copy the file name to the folder name textbox *****/
            //           var AlertMsg= "Add text to DMS path ?";
            //           var res = confirm(AlertMsg);
            //            
            //           if (res==true)
            //           {      
            //                                               
            //                var strFolder_Name = str.substring(0,n);                                        
            //                var Obj_DMS_Folder_Name = document.getElementById('<%=tbDMS_Folder_Name.ClientID%>');                        
            //                
            //                //Though the File name Empty if User Click Ok then Folder Name also blank
            //                Obj_DMS_Folder_Name.value = strFolder_Name;                                            
            //                if(strFolder_Name !="")
            //                {
            //                   Obj_DMS_Folder_Name.value = Obj_DMS_Folder_Name.value +"/";                                            
            //                }                                        
            //           }
        }
        function Open_Resume_DMS_Path() {

            document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value = alltrim(document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value);
            document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value);
            document.getElementById('<%=tbResume_File_Name.ClientID%>').value = alltrim(document.getElementById('<%=tbResume_File_Name.ClientID%>').value);

            if (document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value == "") {
                alert("Resume Path must be entered");
                document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').focus();
                return false;
            }



            if (document.getElementById('<%=tbResume_File_Name.ClientID%>').value == "") {
                alert("File name must be entered");
                document.getElementById('<%=tbResume_File_Name.ClientID%>').focus();
                return false;
            }

            Check_Slash_strEnd(document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>'));

            var Resume_File_Full_Path = document.getElementById('<%=tbDMS_Path_QHSE.ClientID%>').value +
            document.getElementById('<%=tbDMS_Folder_Name.ClientID%>').value +
            document.getElementById('<%=tbResume_File_Name.ClientID%>').value;

            window.open(Resume_File_Full_Path, '_blank', 'left=0,top=0,height=2000,width=2000, resizable=yes, status=yes');

            return false;
        }
        function Check_Slash_strEnd(Obj_DMS_Path) {

            if (Obj_DMS_Path.value != "") {
                var Str = Obj_DMS_Path.value;
                Str = Str.substring(Str.length - 1, Str.length);
                if (Str != "/") {
                    Obj_DMS_Path.value = Obj_DMS_Path.value + "/";
                }
            }

        }
    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmIncident_Details" runat="server">
    <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
        <table style="width: 100%" class="table_header">
            <tr>
                 
                <td class="td_button">
                    <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" OnClientClick="Show_Main_Data();return false;"
                        CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnAdd" runat="server" Text="Add" Width="100%" OnClick="btnAdd_Click"
                        OnClientClick="return validate('ADD');" CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnUpdate" runat="server" Text="Update" Width="100%" CssClass="td_button"
                        OnClientClick="return validate('UPDATE');" OnClick="btnUpdate_Click" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnDelete" runat="server" Text="Delete" Width="100%" CssClass="td_button"
                     OnClientClick="return validate('DELETE');" OnClick="btnDelete_Click" Height="21px" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                        OnClick="btnClear_Click" OnClientClick="return SetPostbackFlag('CLEAR');" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnPrint" runat="server" Text="Print" Width="100%" CssClass="td_button"
                        OnClientClick="return Validate_Print();" OnClick="btnPrint_Click" />
                </td>
                <td class="td_button">
                    &nbsp;
                </td>
                <td class="td_header" style="width: 40%">
                    INCIDENT DETAILS
                </td>
            </tr>
        </table>
        <br />
        <div id='divbgPopup'   style= 'visibility :hidden;  background-color :#ffd2af; overflow :hidden ; border :1px solid #FF0000; position:absolute ; width: 256px; height: 114px; top: 150px; right: 544px; bottom: 334px; clip: rect(100px, 500px, auto, 200px); left: 470px; z-index:100; margin-right: 0px;'>
             
                <table>
                    <tr>
                        <td class="td_caption" style ="text-align :left" >Reason for Delete  (100 chars.)</td>
                    </tr>
                    <tr >
                        <td colspan ="2">
                            <asp:TextBox ID="tbDeleted_Remarks" runat="server" CssClass="textbox" Width="250px"
                                onkeyPress="CheckMaxLen(this,100);" TextMode="MultiLine" Height="50px" onblur="return fncMultilineTBOnBlur(this,100);"></asp:TextBox>
                        </td>
                    </tr>
                    <tr >
                        <td  style="vertical-align :central ">
                            <asp:Button ID="btnDelete_Ok_Final" runat="server" Text="Ok" Width="20%"  
                                OnClientClick="return validate('DELETE_OK');" CssClass="td_button" OnClick="btnDelete_Ok_Final_Click" />
                      
                            <asp:Button ID="btnDelete_Cancel_Final" runat="server" Text="Cancel" Width="20%"  
                                OnClientClick="return validate('DELETE_CANCEL');" CssClass="td_button" />
                        </td>
                    </tr>
                </table>
            </div>
        <table cellpadding="0" cellspacing="0" class="table">
            <tr>
                <td class="td_panel" style="width: 20%">
                    Version: 10.0</td>

                 
                    <td class="td" colspan="3">
                        <asp:LinkButton ID="lbtnDownload" runat="server" OnClick="lbtnDownload_Click">Download Incident Details Template</asp:LinkButton>
                    </td>
               
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr id="tr_Exel_Upload" runat="server">
                <td class="td" style="vertical-align: top;" colspan="2">
                    <asp:FileUpload ID="fupd_ExcelSheet" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                        Width="65%" Height="20px" />
                    <asp:Button ID="btnUpload" runat="server" Text="Upload Excel File" CssClass="td_button"
                        Width="125px" OnClientClick="return Check_File_Selected('REC');" OnClick="btnUpload_Click" />
                </td>
                <%--                <td class="td" style="vertical-align: top;">
                    <asp:Button ID="btnUpload" runat="server" Text="Upload Excel File" CssClass="td_button"
                        Width="125px" OnClientClick="return Check_File_Selected('REC');" OnClick="btnUpload_Click" />
                </td>--%>
                <td colspan="2">
                </td>
            </tr>
            <tr>
                <td class="td" style="vertical-align: top;" colspan="2">
                    <div id="div1" class="div_gridview" style="width: 75%; height: 100px">
                        <asp:GridView ID="grdUploaded_Images" runat="server" AutoGenerateColumns="False"
                            CssClass="GridView" Width="95%" OnRowDataBound="grdUploaded_Images_RowDataBound">
                            <Columns>
                                <asp:TemplateField HeaderStyle-CssClass="hiddencol" HeaderText="tbIncident_Photo_Id_Hidden"
                                    ItemStyle-CssClass="hiddencol">
                                    <ItemTemplate>
                                        <input id="tbIncident_Photo_Id_Hidden" runat="server" name="tbIncident_Photo_Id_Hidden"
                                            style="z-index: 104; left: 43px; width: 24px; position: absolute; top: 258px;
                                            height: 24px" type="hidden" value='<%# Bind("Incident_Photo_Id") %>' />
                                    </ItemTemplate>
                                    <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                                    <ItemStyle CssClass="hiddencol"></ItemStyle>
                                </asp:TemplateField>
                                <asp:TemplateField HeaderStyle-CssClass="hiddencol" HeaderText="tbIncident_Photo_Id_Hidden"
                                    ItemStyle-CssClass="hiddencol">
                                    <ItemTemplate>
                                        <input id="tbIncident_Photo_Path_Hidden" runat="server" name="tbIncident_Photo_Path_Hidden"
                                            style="z-index: 104; left: 43px; width: 24px; position: absolute; top: 258px;
                                            height: 24px" type="hidden" value='<%# Bind("Incident_Photo_Path") %>' />
                                    </ItemTemplate>
                                    <HeaderStyle CssClass="hiddencol"></HeaderStyle>
                                    <ItemStyle CssClass="hiddencol"></ItemStyle>
                                </asp:TemplateField>
                                <asp:BoundField DataField="Sr_No" HeaderText="Sr.No.">
                                    <ItemStyle Width="20px" HorizontalAlign="Center" />
                                    <HeaderStyle HorizontalAlign="Center"></HeaderStyle>
                                </asp:BoundField>
                                <asp:TemplateField HeaderText="Image">
                                    <ItemTemplate>
                                        <a href="#" id="lnkDisp_Img" runat="server">Show</a>
                                    </ItemTemplate>
                                </asp:TemplateField>
                                <asp:BoundField DataField="Incident_File_Name" HeaderText="Uploaded Images ">
                                    <ItemStyle Width="50%" HorizontalAlign="left" />
                                    <HeaderStyle HorizontalAlign="left"></HeaderStyle>
                                </asp:BoundField>
                                <asp:TemplateField AccessibleHeaderText="chkSelect" HeaderText="Remove">
                                    <ItemTemplate>
                                        <input id="chkSelect" runat="server" tooltip="Click here to Remove image" type="checkbox" />
                                    </ItemTemplate>
                                </asp:TemplateField>
                            </Columns>
                            <RowStyle CssClass="GridView_RowStyle" />
                            <HeaderStyle  CssClass="GridView_HeaderStyle" Height="20px" />
                            <AlternatingRowStyle CssClass="GridView_AlternatingRowStyle" />
                            <SelectedRowStyle CssClass="GridView_FooterStyle" />
                            <FooterStyle CssClass="GridView_FooterStyle" />
                        </asp:GridView>
                    </div>
                </td>
                <td colspan="2">
                    <div id="divHelpData" class="div_gridview" style="width: 75%; height: 100px">
                        <asp:GridView ID="grdInc_Images" runat="server" AutoGenerateColumns="False" CssClass="GridView"
                            Width="95%">
                            <Columns>
                                <asp:BoundField DataField="Sr_No" HeaderText="Sr.No.">
                                    <ItemStyle Width="20px" HorizontalAlign="Center" />
                                    <HeaderStyle HorizontalAlign="Center"></HeaderStyle>
                                </asp:BoundField>
                                <asp:TemplateField HeaderText="Upload Incident Photos">
                                    <ItemTemplate>
                                        <asp:FileUpload ID="fupd_Inc_Images" CssClass="textbox_readonly" onkeydown="return false;"
                                            name="uploadFile" onchange="return SetPostbackFlag('IMG_UPLOAD');return  Chk_Inc_Ext_Duplicate_File(this);"
                                            runat="server" Width="95%" Height="20px" />
                                    </ItemTemplate>
                                </asp:TemplateField>
                                <asp:TemplateField>
                                    <ItemTemplate>
                                        <asp:Button ID="Button1" runat="server" Text="Clear" OnClientClick="return Clear_Image_Path(this);  " />
                                    </ItemTemplate>
                                </asp:TemplateField>
                            </Columns>
                            <RowStyle CssClass="GridView_RowStyle" />
                            <HeaderStyle  CssClass="GridView_HeaderStyle" Height="20px" />                            <AlternatingRowStyle CssClass="GridView_AlternatingRowStyle" />
                            <SelectedRowStyle CssClass="GridView_FooterStyle" />
                            <FooterStyle CssClass="GridView_FooterStyle" />
                        </asp:GridView>
                    </div>
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>

                <% if(tbIncident_Id_Hidden.Value !=""){ %>
                <td class="td_caption">
                    Incident No.</td>
                <td class="td">
                    <asp:TextBox ID="tbIncident_No" runat="server" CssClass="textbox_right_readonly"
                        Width="50px" OnKeyDown="return RejectInput();" MaxLength="1"></asp:TextBox>
                     
                </td>
                <td class="td_caption">
                </td>
                <td class="td">
                </td>
                <%} %>
            </tr>
            <tr>
                <td class="td_caption" style="vertical-align: top">
                    Rig Incident No.
                </td>
                <td class="td" style="vertical-align: top">
                    <asp:TextBox ID="tbRig_Incident_No" runat="server" CssClass="textbox" Width="150px"
                        MaxLength="20"></asp:TextBox>
                </td>
                <td class="td_caption" >
                    <span class="star">* </span>Incident Belongs To
                </td>
                <td class="td">
                    <asp:DropDownList ID="ddlIncident_Party" runat="server" CssClass="dropdownlist" >
                        <asp:ListItem Value=""> </asp:ListItem>
                        <asp:ListItem Value="10">OGDSL</asp:ListItem>
                        <asp:ListItem Value="30">EOSL</asp:ListItem>
                        <asp:ListItem Value="308">StarBit</asp:ListItem>                            
                        <asp:ListItem Value="309">OGD-EHES JVPL</asp:ListItem>                            
                        <asp:ListItem Value="316">Seros</asp:ListItem>                            
                                           
                        <asp:ListItem Value="2">Operator</asp:ListItem>
                        <asp:ListItem Value="1">Operator Contractors</asp:ListItem>                    
                        <asp:ListItem Value="0">TP Contractors</asp:ListItem>
                    </asp:DropDownList>
                </td>
            </tr>
            <tr>
                <td class="td_caption" >
                    Rig
                </td>
                <td class="td" >
                    <asp:TextBox ID="tbRig" runat="server" CssClass="textbox_readonly" MaxLength="1"
                        Width="105px" OnKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnRig" runat="server" OnClientClick="Show_Rig();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Vessel" CssClass="image_search" />
               
                    <img id="imgOperator_Name0" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbRig.ClientID %>', '<%= tbRig_Id_Hidden.ClientID %>')" /></td>
                <td class="td_caption">
                    Unit
                </td>
                <td class="td">
                    <asp:TextBox ID="tbUnit_Name" runat="server" CssClass="textbox" Width="240px" MaxLength="35"
                        onKeyUp="Check_Input(this);"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption"  >
                    <span class="star">*</span>&nbsp;Incident : Date/Time - No
                </td>
                <td class="td"  >
                 
                    <asp:TextBox ID="tbIncident_Date" runat="server" CssClass="textbox" MaxLength="10"
                        AutoPostBack="true" Width="70px" OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);"
                        AutoCompleteType="Disabled" OnTextChanged="tbIncident_Date_TextChanged"></asp:TextBox>
                    &nbsp;<asp:TextBox ID="tbIncident_Time" runat="server" CssClass="textbox" Width="40px"
                        OnKeyUp="return TimeMask(this);" OnBlur=" return CheckTimeOnBlur(this)" MaxLength="5"></asp:TextBox>&nbsp;</td>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Incident Reported: Date/Time
                </td>
                <td class="td">
                    <asp:TextBox ID="tbIncident_Reported_Dt" runat="server" CssClass="textbox" MaxLength="10"
                        Width="70px" OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);"
                        AutoCompleteType="Disabled"></asp:TextBox>
                    &nbsp;<asp:TextBox ID="tbIncident_Reported_Time" runat="server" CssClass="textbox"
                        Width="40px" OnKeyUp="return TimeMask(this);" OnBlur=" return CheckTimeOnBlur(this)"
                        MaxLength="5"></asp:TextBox>&nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Location
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    Well No.
                </td>
                <td class="td">
                    <asp:TextBox ID="tbWell_No" runat="server" CssClass="textbox" Width="150px" MaxLength="20"></asp:TextBox>
                </td>
                <td class="td_caption" style="width: 15%;">
                    &nbsp;Country
                </td>
                <td class="td">
                    <asp:TextBox ID="tbCountry_Name" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                        Width="242px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtnCountry"
                            runat="server" OnClientClick="ShowCountry();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Country" CssClass="image_search" />
                    <img id="imgCountry_Name" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbCountry_Name.ClientID %>', '<%= tbCountry_Id_Hidden.ClientID %>')" />
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    Operator
                </td>
                <td class="td">
                    <asp:TextBox ID="tbOperator_Name" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                        Width="250px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtntbOperator"
                            runat="server" OnClientClick="Show_Operator();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find FS Employee" CssClass="image_search" />
                    <img id="imgOperator_Name" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbOperator_Name.ClientID %>', '<%= tbOperator_Id_Hidden.ClientID %>')" />
                </td>
                <td class="td_caption">
                    &nbsp;
                </td>
                <td class="td">
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    Drilling Superintendent
                </td>
                <td class="td">
                    <asp:TextBox ID="tbDrilling_Superintendent" runat="server" CssClass="textbox" Width="250px"
                        MaxLength="40" onKeyUp="Check_Input(this);"></asp:TextBox>
                </td>
                <td class="td_caption">
                    Safety Officer
                </td>
                <td class="td">
                    <asp:TextBox ID="tbSafety_Officer" runat="server" CssClass="textbox" Width="250px"
                        MaxLength="40" onKeyUp="Check_Input(this);"></asp:TextBox>
                </td>
            </tr>
             
            <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Nature
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Nature of Accident/Incident
                </td>
                <td class="td">
                    <asp:TextBox ID="tbIncident_Type" runat="server" CssClass="textbox_readonly" MaxLength="1"
                        OnKeyDown="return RejectInput();" Width="315px"></asp:TextBox>&nbsp<asp:ImageButton
                            ID="ibtnIncident_Type" runat="server" OnClientClick="Show_Incident_Type(); return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Incident Type"
                            CssClass="image_search" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    <span class="star">*</span>&nbsp;Incident Severity :Actual
                </td>
                <td class="td">
                    <asp:DropDownList ID="ddlIncident_Severity_Actual" runat="server" CssClass="dropdownlist">
                        <asp:ListItem Value="L">Low</asp:ListItem>
                        <asp:ListItem Value="M">Medium</asp:ListItem>
                        <asp:ListItem Value="H">High</asp:ListItem>
                    </asp:DropDownList>
                </td>
                <td class="td_caption" height="50px">
                    <span class="star">*</span>&nbsp;Potential
                </td>
                <td class="td">
                    <asp:DropDownList ID="ddlIncident_Severity_Potential" runat="server" CssClass="dropdownlist">
                        <asp:ListItem Value="L">Low</asp:ListItem>
                        <asp:ListItem Value="M">Medium</asp:ListItem>
                        <asp:ListItem Value="H">High</asp:ListItem>
                    </asp:DropDownList>
                </td>
            </tr>
     
            <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Injury
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    &nbsp;Person Injured
                </td>
                <td class="td">
                    <asp:DropDownList ID="ddlPerson_Injured" runat="server" CssClass="dropdownlist" onchange="Disp_Person_Injured();">
                        <asp:ListItem Value="Y">Y</asp:ListItem>
                        <asp:ListItem Value="N">N</asp:ListItem>
                    </asp:DropDownList>
                </td>
                <td class="td_caption" height="50px">
                    Belongs To
                </td>
                <td class="td">
                    <asp:DropDownList ID="ddlThird_Party" runat="server" CssClass="dropdownlist" onchange="Disp_Contractor();">
                        <asp:ListItem Value=""> </asp:ListItem>
                        <asp:ListItem Value="10">OGDSL</asp:ListItem>
                        <asp:ListItem Value="30">EOSL</asp:ListItem>
                        <asp:ListItem Value="308">StarBit</asp:ListItem>    
                        <asp:ListItem Value="309">OGD-EHES JVPL</asp:ListItem>       
                          <asp:ListItem Value="316">Seros</asp:ListItem>                            
                                          
                        <asp:ListItem Value="2">Operator</asp:ListItem>
                        <asp:ListItem Value="1">Operator Contractors</asp:ListItem>
                        <asp:ListItem Value="0">TP Contractors</asp:ListItem>
                    </asp:DropDownList>
                    <!-- 10,30,308 : are company ids and 0,1,2 : are just distinct values--->
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    TP Contractor Name
                </td>
                <td class="td">
                    <asp:TextBox ID="tbContractor_Name" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                        Width="250px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtnContractor"
                            runat="server" OnClientClick="Show_Contractor();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find FS Employee" CssClass="image_search" />
                </td>
                <td class="td_caption" height="50px">
                    &nbsp;
                </td>
                <td class="td">
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    Name of Person
                </td>
                <td class="td">
                    <asp:TextBox ID="tbEmp_Name" runat="server" CssClass="textbox" Width="360px" MaxLength="75"
                        onKeyUp="Check_Input(this);"></asp:TextBox>
                </td>
                <td class="td_caption">
                    Designation
                </td>
                <td class="td">
                    <asp:TextBox ID="tbRank_Name" runat="server" CssClass="textbox_disabled" Width="250px"
                        MaxLength="1"></asp:TextBox>
                    <asp:ImageButton ID="ibtnRank" runat="server" OnClientClick="ShowRank('Injure'); return false;"
                        ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Rank"
                        CssClass="image_search" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    Total Rig/Field Exp in months
                </td>
                <td class="td">
                    <asp:TextBox ID="tbTotal_Rig_Exp_Months" runat="server" CssClass="textbox_right"
                        onKeyUp="Validate_Numeric(this);" onblur="return checkNum(this,3,0);" MaxLength="3"
                        Width="27px"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    Part Of Body Injured 1
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPart_Of_Body_Name_1" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" OnKeyDown="return RejectInput();" Width="315px"></asp:TextBox>&nbsp<asp:ImageButton
                            ID="ibtnPart_Of_Body_Name_1" runat="server" OnClientClick="Show_Injured_Parts_1(); return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Incident Type"
                            CssClass="image_search" />
                    <img id="imgPart_Of_Body_Name_1" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbPart_Of_Body_Name_1.ClientID %>', '<%= tbPart_Of_Body_Id_Hidden_1.ClientID %>')" />
                </td>
                <td class="td_caption">
                    &nbsp;&nbsp;&nbsp;&nbsp; Part Of Body Injured 2
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPart_Of_Body_Name_2" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" OnKeyDown="return RejectInput();" Width="315px"></asp:TextBox>&nbsp<asp:ImageButton
                            ID="ibtnPart_Of_Body_Name_2" runat="server" OnClientClick="Show_Injured_Parts_2(); return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Incident Type"
                            CssClass="image_search" />
                    <img id="imgPart_Of_Body_Name_2" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbPart_Of_Body_Name_2.ClientID %>', '<%= tbPart_Of_Body_Id_Hidden_2.ClientID %>')" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" height="50px">
                    Part Of Body Injured 3
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPart_Of_Body_Name_3" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" OnKeyDown="return RejectInput();" Width="315px"></asp:TextBox>&nbsp<asp:ImageButton
                            ID="ibtnPart_Of_Body_Name_3" runat="server" OnClientClick="Show_Injured_Parts_3(); return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Incident Type"
                            CssClass="image_search" />
                    <img id="imgPart_Of_Body_Name_3" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbPart_Of_Body_Name_3.ClientID %>', '<%= tbPart_Of_Body_Id_Hidden_3.ClientID %>')" />
                </td>
                <td class="td_caption">
                    &nbsp;&nbsp;&nbsp;&nbsp; Part Of Body Injured 4
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPart_Of_Body_Name_4" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" OnKeyDown="return RejectInput();" Width="315px"></asp:TextBox>&nbsp<asp:ImageButton
                            ID="ibtnPart_Of_Body_Name_4" runat="server" OnClientClick="Show_Injured_Parts_4(); return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Incident Type"
                            CssClass="image_search" />
                    <img id="imgPart_Of_Body_Name_4" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbPart_Of_Body_Name_4.ClientID %>', '<%= tbPart_Of_Body_Id_Hidden_4.ClientID %>')" />
                </td>
            </tr>
              <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Causes
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Description
                    <br />
                    (1000 chars)
                </td>
                <td class="td">
                    <asp:TextBox ID="tbIncident_Descr" runat="server" CssClass="textbox" Width="350px"
                        onkeyPress="CheckMaxLen(this,1000);" TextMode="MultiLine" Height="50px" onblur="return fncMultilineTBOnBlur(this,1000);"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="vertical-align: top">
                    <span class="star">*</span>&nbsp;Immediate Cause
                </td>
                <td class="td" style="vertical-align: top">
                    <asp:TextBox ID="tbImmediate_Cause_1" runat="server" CssClass="textbox_readonly"
                        Width="360px" OnKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnImmediate_Incident_Cause_1" runat="server" OnClientClick="Show_Immediate_Incident_Cause('1');return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Immediate Incident Cause"
                            CssClass="image_search" />
                </td>
                <td class="td_caption" style="vertical-align: top">
                    <span class="star">&nbsp;</span>&nbsp;Immediate Cause 2
                </td>
                <td class="td" style="vertical-align: top">
                    <asp:TextBox ID="tbImmediate_Cause_2" runat="server" CssClass="textbox_readonly"
                        Width="340px" OnKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnImmediate_Incident_Cause_2" runat="server" OnClientClick="Show_Immediate_Incident_Cause('2');return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Immediate Incident Cause"
                            CssClass="image_search" />
                    <img id="imgImmediate_Incident_Cause_2" src="../Images/Icons/Clearfield.jpg" title="Clear Field"
                        style="cursor: pointer; height: 20px;" onclick="javascript:return clearInput('<%= tbImmediate_Cause_2.ClientID %>', '<%= tbImmediate_Incident_Cause_Id_2_Hidden.ClientID %>')" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="vertical-align: top">
                    Immediate Cause Description<br />
                    (500 chars)
                </td>
                <td class="td" style="vertical-align: top; margin-left: 40px;">
                    <asp:TextBox ID="tbImmediate_Cause_Descr" runat="server" CssClass="textbox" onkeyPress="CheckMaxLen(this,500);"
                        Height="50px" onblur="return fncMultilineTBOnBlur(this,500);" TextMode="MultiLine"
                        Width="350px"></asp:TextBox>
                </td>
            </tr>
             <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Actions
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Rig Operation
                </td>
                <td class="td">
                    <asp:TextBox ID="tbRig_Operation_Name" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" Width="360px" OnKeyDown="return RejectInput();"></asp:TextBox>
                    <asp:ImageButton ID="ibtnRig_Opeartion" runat="server" CssClass="image_search" ImageAlign="Middle"
                        ImageUrl="~/Images/Icons/search.gif" OnClientClick="Show_Rig_Operation(); return false;"
                        ToolTip="Find Work Location" />
                </td>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Work Location
                </td>
                <td class="td">
                    <asp:TextBox ID="tbWork_Location_Name" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" Width="360px" OnKeyDown="return RejectInput();"></asp:TextBox>
                    <asp:ImageButton ID="ibtnWork_Location" runat="server" CssClass="image_search" ImageAlign="Middle"
                        ImageUrl="~/Images/Icons/search.gif" OnClientClick="Show_Work_Location(); return false;"
                        ToolTip="Find Work Location" />
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    <span class="star">*</span>&nbsp;Contact / Exposure Type
                </td>
                <td class="td">
                    <asp:TextBox ID="tbContact_Expo_Type_Name" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" Width="210px" OnKeyDown="return RejectInput();"></asp:TextBox>
                    <asp:ImageButton ID="ibtntbContact_Expo_Type" runat="server" CssClass="image_search"
                        ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" OnClientClick="Show_Contact_Exposure_Type(); return false;"
                        ToolTip="Find Work Location" Width="20px" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="vertical-align: top">
                    Corrective Action
                    <br />
                    (300 chars)
                </td>
                <td class="td">
                    <asp:TextBox ID="tbCorrective_Action" runat="server" CssClass="textbox" onkeyPress="CheckMaxLen(this,300);"
                        onblur="return fncMultilineTBOnBlur(this,300);" Height="50px" TextMode="MultiLine"
                        Width="350px"></asp:TextBox>
                </td>
                <td class="td_caption" style="vertical-align: top">
                    Preventive Action
                    <br />
                    (250 chars)
                </td>
                <td class="td">
                    <asp:TextBox ID="tbPreventive_Action" runat="server" CssClass="textbox" onkeyPress="CheckMaxLen(this,250);"
                        Height="50px" onblur="return fncMultilineTBOnBlur(this,250);" TextMode="MultiLine"
                        Width="350px"></asp:TextBox>
                </td>
            </tr>
               <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Financials
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="height: 9px">
                    Loss in Hrs : NPT
                </td>
                <td class="td" style="height: 9px">
                    <asp:TextBox ID="tbNPT_Hrs_Loss" runat="server" CssClass="textbox_right" MaxLength="6"
                        onblur="return checkNum(this,5,2);" onKeyUp="Validate_Decimal(this);" Width="50px"></asp:TextBox>
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Manhours&nbsp;
                    <asp:TextBox ID="tbManhours_Loss" runat="server" CssClass="textbox_right" MaxLength="6"
                        onblur="return checkNum(this,5,2);" onKeyUp="Validate_Decimal(this);" Width="50px"></asp:TextBox>
                </td>
               
            </tr>
            <tr>
                <td class="td_caption">
                    Currency
                </td>
                <td class="td">
                    <asp:TextBox ID="tbFinancial_Loss_Currency" runat="server" CssClass="textbox_readonly"
                        MaxLength="1" Width="62px" OnKeyDown="return RejectInput();"></asp:TextBox>&nbsp;<asp:ImageButton
                            ID="ibtnFinancial_Loss_Currency_Id" runat="server" OnClientClick="Show_Currency();return false;"
                            ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Currency"
                            CssClass="image_search" />
                </td>
                <td class="td_caption">
                    Financial Loss Amount
                </td>
                <td class="td">
                    <asp:TextBox ID="tbFinancial_Loss_Amt" runat="server" CssClass="textbox_right" MaxLength="7"
                        Width="50px"></asp:TextBox>
                </td>
            </tr>
            
            <tr runat="server" visible="false">
                <td class="td_caption">
                    Exchange Rate
                </td>
                <td class="td">
                    <asp:TextBox ID="tbExchange_Rate" runat="server" MaxLength="7" CssClass="textbox_right_readonly"
                        onKeyDown="return RejectInput();" Width="55px"></asp:TextBox>
                </td>
                <td class="td_caption">
                    Financial Loss <span style="font-family: Rupee Foradian; font-size: 12px">`</span>
                    Amount
                </td>
                <td class="td">
                    <asp:TextBox ID="tbFinancial_Loss_BC_Amt" runat="server" MaxLength="13" Width="102"
                        CssClass="textbox_right_readonly" onKeyDown="return RejectInput();"></asp:TextBox>
                </td>
            </tr>
              <tr>
                <td>
                    &nbsp;
                </td>
            </tr>
            <tr>
                <td class="td_section" style="width: 20%">
                    Reporting
                </td>
            </tr>
            <tr>
                <td class="td_caption">
                    Employee
                </td>
                <td class="td">
                    <asp:TextBox ID="tbReported_By" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                        Width="250px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtnFs_Emp_Name"
                            runat="server" OnClientClick="ShowFsEmployee();return false;" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" ToolTip="Find FS Employee" CssClass="image_search" />
                </td>
                <td class="td_caption">
                    Rank
                </td>
                <td class="td">
                    <asp:TextBox ID="tbRptd_By_Rank_Name" runat="server" CssClass="textbox_disabled"
                        Width="250px" MaxLength="1"></asp:TextBox>
                    <asp:ImageButton ID="ibtnRptd_By_Rank_Name" runat="server" OnClientClick="ShowRank('Rpted'); return false;"
                        ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif" ToolTip="Find Rank"
                        CssClass="image_search" />
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="vertical-align: top">
                    Comments
                    <br />
                    (200 chars)
                </td>
                <td class="td">
                    <asp:TextBox ID="tbComments" runat="server" CssClass="textbox" Width="350px" onkeyPress="CheckMaxLen(this,250);"
                        TextMode="MultiLine" Height="50px" onblur="return fncMultilineTBOnBlur(this,250);"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <tr>
                <td class="td_caption" valign="top">
                    DMS Path
                </td>
                <td class="td" colspan="7">
                    <asp:TextBox ID="tbDMS_Path_QHSE" runat="server" CssClass="textbox_readonly" Width="750px"
                        onKeyDown="return RejectInput()" onfocus="Set_DMS_Path();" onblur="Check_DMS_Path(this,19,'B');"></asp:TextBox>
                    &nbsp;
                    <br />
                </td>
            </tr>
            <tr>
                <td class="td_caption" valign="top">
                    Folder
                </td>
                <td class="td" colspan="7">
                    <asp:TextBox ID="tbDMS_Folder_Name" runat="server" CssClass="textbox" Width="400px"
                        onfocus="Set_DMS_Path();"  onchange="Check_FolderPath(this);"></asp:TextBox>
                    &nbsp; File&nbsp;<asp:TextBox ID="tbResume_File_Name" runat="server" CssClass="textbox"
                        Width="250px" onfocus="Set_DMS_Path();" onchange="Check_Folder(this);"></asp:TextBox><asp:Button
                            ID="btnShowBusiness_Report_DMS_Path" runat="server" Text="View" CssClass="td_button"
                            OnClientClick="Open_Resume_DMS_Path();return false;" Width="55px" />
                </td>
            </tr>
            <%--Dummy Button is created in last row for mutline TB focus to set back to it if Onblur fnc validate ,as js fnc not allowing focus for last row Multiline TB--%>
            <tr>
                <td>
                </td>
                <td class="td">
                    <asp:Button ID="btnDummy1" runat="server" CssClass="td_button" OnClientClick="return false"
                        Width="1px" />
                </td>
                <td>
                </td>
                <td>
                </td>
            </tr>
            <tr>
                <td class="td_line" colspan="4">
                </td>
            </tr>
            <%--------------------------------------------------------------------------------------------------------------------------------------------------------------%>
        </table>
        <br />
        <input id="tbPart_Of_Body_Id_Hidden_1" runat="server" name="tbPart_Of_Body_Id_Hidden_1"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbPart_Of_Body_Id_Hidden_2" runat="server" name="tbPart_Of_Body_Id_Hidden_2"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbPart_Of_Body_Id_Hidden_3" runat="server" name="tbPart_Of_Body_Id_Hidden_3"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbPart_Of_Body_Id_Hidden_4" runat="server" name="tbPart_Of_Body_Id_Hidden_4"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbIncident_Id_Hidden" runat="server" name="tbIncident_Id_Hidden" style="z-index: 104;
            left: 23px; width: 24px; position: absolute; top: 290px; height: 24px" type="hidden" />
        <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden" style="z-index: 104;
            left: 68px; width: 24px; position: absolute; top: 291px; height: 24px" type="hidden" />
        <input id="tbCountry_Id_Hidden" runat="server" name="tbCountry_Id_Hidden" style="z-index: 104;
            left: 280px; width: 24px; position: absolute; top: 269px; height: 24px" type="hidden" />
        <input id="tbOperator_Id_Hidden" runat="server" name="tbOperator_Id_Hidden" style="z-index: 104;
            left: 280px; width: 24px; position: absolute; top: 269px; height: 24px" type="hidden" />
        <input id="tbContractor_Id_Hidden" runat="server" name="tbContractor_Id_Hidden" style="z-index: 104;
            left: 280px; width: 24px; position: absolute; top: 269px; height: 24px" type="hidden" />
        <input id="tbIncident_Type_Id_Hidden" runat="server" name="tbIncident_Type_Id_Hidden"
            style="z-index: 104; left: 7px; width: 24px; position: absolute; top: 87px; height: 24px"
            type="hidden" />
        <input id="tbRptd_By_Rank_Id_Hidden" runat="server" name="tbRptd_By_Rank_Id_Hidden"
            style="z-index: 104; left: 7px; width: 24px; position: absolute; top: 87px; height: 24px"
            type="hidden" />
        <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104;
            left: 165px; width: 24px; position: absolute; top: 291px; height: 24px" type="hidden" />
        <input id="tbFinancial_Loss_Currency_Id_Hidden" runat="server" name="tbIncident_Id_Hidden"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbImmediate_Incident_Cause_Id_1_Hidden" runat="server" name="tbImmediate_Incident_Cause_Id_1_Hidden"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbImmediate_Incident_Cause_Id_2_Hidden" runat="server" name="tbImmediate_Incident_Cause_Id_2_Hidden"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbWork_Location_Id_Hidden" runat="server" name="tbWork_Location_Id_Hidden"
            style="z-index: 104; left: 188px; width: 24px; position: absolute; top: 181px;
            height: 24px" type="hidden" />
        <input id="tbRig_Operation_Id_Hidden" runat="server" name="tbRig_Operation_Id_Hidden"
            style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px;
            height: 24px" type="hidden" />
        <input id="tbContact_Expo_Type_Id_Hidden" runat="server" name="tbContact_Expo_Type_Id_Hidden"
            style="z-index: 104; left: 188px; width: 24px; position: absolute; top: 181px;
            height: 24px" type="hidden" />
        <input id="tbMaxExchangeRate_Hidden" runat="server" name="tbMaxExchangeRate_Hidden"
            style="z-index: 104; left: 152px; width: 24px; position: absolute; top: 390px;
            height: 24px" type="hidden" />
        <input id="tbFs_Emp_Id_Hidden" runat="server" name="tbFs_Emp_Id_Hidden" style="z-index: 104;
            left: 115px; width: 24px; position: absolute; top: 293px; height: 24px" type="hidden"
            value="" />
        <input id="tbRank_Id_Hidden" runat="server" name="tbRank_Id_Hidden" style="z-index: 104;
            left: 141px; width: 24px; position: absolute; top: 688px; height: 24px" type="hidden"
            value="" />
        <input id="tbWkg_Incident_Dtl_Id_Hidden" runat="server" name="tbWkg_Incident_Dtl_Id_Hidden"
            style="z-index: 104; left: 188px; width: 24px; position: absolute; top: 181px;
            height: 24px" type="hidden" />
    </div>
    </form>
</body>
</html>
