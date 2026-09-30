<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmHazard_ID_Card.aspx.cs"
    Inherits="Quality_And_Safety_frmHazard_ID_Card" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>Hazard ID Card</title>
     <link href="../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/CommonModal.js"></script>
    
    <link href="../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />  

    <script type="text/javascript">
        window.onload = function () {   }
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

                if (document.getElementById('<%=tbHaz_Card_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'You are currently in Delete mode. A new record cannot be deleted in this mode.');
                    return false;
                }

                if (document.getElementById("divbgPopup").style.visibility == "hidden") {
                    var res = confirm("Are you sure you want to Delete this Record ?");
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
                if (document.getElementById('<%=tbHaz_Card_Id_Hidden.ClientID%>').value != "") {
                    ShowMessage(400, 75, 'You are currently in Update mode. A new record cannot be added in this mode.');
                    return false;
                }


            }
            else /// UPDATE
            {
                /// Blocking ADD button when an existing record is selected.
                if (document.getElementById('<%=tbHaz_Card_Id_Hidden.ClientID%>').value == "") {
                    ShowMessage(400, 75, 'Select record to Update.');
                    return false;
                }
                //                else
                //                {
                //                    ShowMessage(400, 75, 'Updation is not allowed.');
                //                    return false;
                //                }

            }

            if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "") {
                msg += "- Rig must be selected<br><br>";
                document.getElementById('<%=ddlRig.ClientID%>').focus();
            }
            if (document.getElementById('<%=tbPrj_Contract_Id_Hidden.ClientID%>').value == "") {
                msg += "- Project No. must be selected<br><br>";
                document.getElementById('<%=tbProject_No_Oper_Location.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbEvent_Dt.ClientID%>').value == "") {
                msg += "- Event Date must be entered<br><br>";
                document.getElementById('<%=tbEvent_Dt.ClientID%>').focus();
            }
            else {

                if (document.getElementById('<%=tbEvent_Dt_Time.ClientID%>').value == "") {
                    msg += "- Event Time must be entered<br><br>";
                    document.getElementById('<%=tbEvent_Dt_Time.ClientID%>').focus();
                }


                if (checkDate(document.getElementById('<%=tbEvent_Dt.ClientID%>').value)) {

                    if (compareDates(document.getElementById('<%=tbEvent_Dt.ClientID%>').value, 'dd/MM/yyyy', strServerDt, 'dd/MM/yyyy') != 0) {
                        msg += "- Event date must be less than or equal to current date<br><br>";
                        document.getElementById('<%=tbEvent_Dt.ClientID%>').focus();
                    }

                }
                else {
                    msg += "- Invalid Event Date<br><br>";
                    document.getElementById('<%=tbEvent_Dt.ClientID%>').focus();
                }
            }


            if (document.getElementById('<%=ddlReported_By_Party.ClientID%>').value == "") {
                msg += "- Reported By Party must be selected<br><br>";
                document.getElementById('<%=ddlReported_By_Party.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbWork_Location_Id_Hidden.ClientID%>').value == "") {
                msg += "- Location must be selected<br><br>";
                document.getElementById('<%=tbWork_Location_Name.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbHaz_Type_Id_Hidden.ClientID%>').value == "") {
                msg += "- Type of Hazard must be selected<br><br>";
                document.getElementById('<%=ddlHaz_Type_Name.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbHazard_Desc.ClientID%>').value == "") {
                msg += "- Hazard Description must be entered<br><br>";
                document.getElementById('<%=tbHazard_Desc.ClientID%>').focus();
            }

            if (document.getElementById('<%=tbResp_Dept_Id_Hidden.ClientID%>').value == "") {
                msg += "- Responsible Dept must be selected<br><br>";
                document.getElementById('<%=ddlResponsible_Dept.ClientID%>').focus();
            }
            if (document.getElementById('<%=tbResp_Rank_Id_Hidden.ClientID%>').value == "") {
                msg += "- Responsible Rank must be selected<br><br>";
                document.getElementById('<%=ddlResponsible_Rank.ClientID%>').focus();
            }


            if (document.getElementById('<%=tbClose_Out_Dt.ClientID%>').value != "") {

                if (compareDates(document.getElementById('<%=tbClose_Out_Dt.ClientID%>').value, 'dd/MM/yyyy', strServerDt, 'dd/MM/yyyy') == 1) {
                    msg += "- Close Out Date cannot be greater than the Current Date<br><br>";
                    document.getElementById('<%=tbClose_Out_Dt.ClientID%>').focus();
                }


                if (checkDate(document.getElementById('<%=tbClose_Out_Dt.ClientID%>').value)) {

                }
                else {
                    msg += "- Invalid Close Out Date<br><br>";
                    document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').focus();
                }


                if (document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').value == "") {
                    msg += "- Close Out Date Time must be entered<br><br>";
                    document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').focus();
                }
                else {

                    if (compareDates(document.getElementById('<%=tbEvent_Dt.ClientID%>').value + ' ' + document.getElementById('<%=tbEvent_Dt_Time.ClientID%>').value, 'dd/MM/yyyy HH:mm',
                        document.getElementById('<%=tbClose_Out_Dt.ClientID%>').value + ' ' + document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').value, 'dd/MM/yyyy HH:mm') == 0) {
                    }
                    else {
                        msg += "- Close Out Date must be greater than Event date<br><br>";
                        document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').focus();
                    }
                }


            }

            if (document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID%>').value == "") {
                msg += "- Hazard ID Card Status must be selected<br><br>";
                document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID%>').focus();
            }
            else {

                if (document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID%>').value == "C") {
                    if (document.getElementById('<%=tbClose_Out_Dt.ClientID%>').value == "") {
                        msg += "- Close Out date must be entered<br><br>";
                        document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').focus();
                    }
                    if (document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').value == "") {
                        msg += "- Close Out time must be entered<br><br>";
                        document.getElementById('<%=tbClose_Out_Dt_Time.ClientID%>').focus();
                    }
                }
            }

            if (msg == "") {
                return true;
            } else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        function Set_Haz_Type_Id() {
            document.getElementById('<%=tbHaz_Type_Id_Hidden.ClientID%>').value = document.getElementById('<%=ddlHaz_Type_Name.ClientID%>').value;
        }
        function Show_Main_Data() {
            SetPostbackFlag("SEARCH");
            Open_Search_Window('HAZARD_ID_CARD', document.forms[0].name, 'tbHaz_Card_Id_Hidden', 'tbProject_No_Oper_Location', '', '', 'Y', 'Y', 'N');
            return;
        }

        function Attach_Events(obj) {
            document.getElementById(obj).className = "textbox_readonly";
            document.getElementById(obj).attachEvent("onkeydown", RejectInput);

            document.getElementById(obj).readOnly = true;
        }
        function Detach_Events(obj) {
            document.getElementById(obj).className = "textbox";
            document.getElementById(obj).detachEvent("onkeydown", RejectInput);

            document.getElementById(obj).readOnly = false;
        }
        function Set_Status() {

            if (document.getElementById('<%=tbClose_Out_Dt.ClientID %>').value != "" &&
                document.getElementById('<%=tbClose_Out_Dt_Time.ClientID %>').value != "") {
                document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID %>').value = "C";
            }
            else {
                if (document.getElementById('<%=tbClose_Out_Dt.ClientID %>').value == "" &&
                document.getElementById('<%=tbClose_Out_Dt_Time.ClientID %>').value == "") {
                    document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID %>').value = "O";
                }
            }
        }

        function Set_Status_Status() {

            if (document.getElementById('<%=tbClose_Out_Dt.ClientID %>').value != "" &&
                 document.getElementById('<%=tbClose_Out_Dt_Time.ClientID %>').value != "") {
                document.getElementById('<%=ddlHaz_ID_Card_Status.ClientID %>').value = "C";
            }
        }
        function set_Emp_Reported_By(strStatus) {
            if (document.getElementById('<%=ddlReported_By_Party.ClientID %>') != null) {

                if (document.getElementById('<%=tbHaz_ID_Card_Status_Hidden.ClientID %>').value == "C") {
                    Attach_Events('tbReported_By_Name');
                }
                else {

                    if (strStatus == 'CNTL') {
                        document.getElementById('<%=tbReported_By_Name.ClientID %>').value = "";
                    }
                    if (document.getElementById('<%=ddlReported_By_Party.ClientID %>').value == "EOSIL") {


                        document.getElementById('ibtnFs_Emp_Namediv').style.display = 'inline';
                        Attach_Events('tbReported_By_Name');

                    }
                    else {
                        Detach_Events('tbReported_By_Name');
                        document.getElementById('ibtnFs_Emp_Namediv').style.display = 'none';
                    }
                }
            }
        }

        function On_Rig_Change() {

            document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value = document.getElementById('<%=ddlRig.ClientID%>').value;

            document.getElementById('<%=tbPrj_Contract_Id_Hidden.ClientID%>').value = "";
            document.getElementById('<%=tbProject_No_Oper_Location.ClientID%>').value = "";

            SetPostbackFlag("RIG");
            // __doPostBack();

        }



        function ShowFsEmployee() {

            if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "")
            {
                alert("Rig must be seleccted ");
                return;
            }
            SetPostbackFlag("FSEMPLOYEE");
            Open_Search_Window('FS_EMPLOYEE', document.forms[0].name, 'tbReported_By_Fs_Emp_Id_Hidden', 'tbReported_By_Name', '', '', 'N', 'Y', 'N');
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

        function Show_Work_Location() {
            SetPostbackFlag("WORK_LOCATION");
            var strSearchString = "%";
            Open_Search_Window('WORK_LOCATION', document.forms[0].name, 'tbWork_Location_Id_Hidden', 'tbWork_Location_Name', '', strSearchString, 'N', 'N', 'N');
            return;
        }

        function check_Clik_Dept_Rank_Rig_Selected(obj) {

            if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "") {
                if (obj.options.length <= 0) {
                    alert("Rig must be selected");
                    return false;
                }
            }

        }

        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }
        function CheckMaxLen(obj, length) {
            checkTextAreaMaxLength(obj, event, length);
        }
        function Set_Reported_Rank_Id(obj) {
            document.getElementById('<%=tbResp_Rank_Id_Hidden.ClientID%>').value = obj.value;
        }

    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmHazard_ID_Card" runat="server">
        &nbsp;
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
                            OnClientClick="return validate('DELETE');"  />
                    </td>
                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                            OnClick="btnClear_Click" OnClientClick="return SetPostbackFlag('CLEAR');" />
                    </td>

                    <td class="td_button"></td>
                    <td class="td_header" style="width: 40%">Hazard ID Card
                    </td>
                </tr>
            </table>
            <br />

            <div id='divbgPopup'   style= 'visibility :hidden;  background-color :#ffd2af;  border :1px solid #FF0000; position: absolute; width: 256px; height: 114px; top: 150px; right: 544px; bottom: 334px; clip: rect(100px, 500px, auto, 200px); left: 470px; z-index: auto; margin-right: 0px;'>
             
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
            <table class="table">
                <tr>
                    <td style="width: 15%"></td>
                    <td style="width: 23%"></td>
                    <td style="width: 12%"></td>
                    <td></td>

                </tr>
                <% if (tbHaz_Card_Id_Hidden.Value != "")
                   {  %>
                <tr>
                    <td class="td_caption">Haz ID Card No
                    </td>
                    <td class="td" style="vertical-align: top">
                        <asp:TextBox ID="tbHaz_ID_Card_No" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();" Width="50px"
                            MaxLength="20"></asp:TextBox>
                    </td>
                </tr>
                <%} %>
                <tr>
                    <td class="td_caption"><span class="star">*</span> Rig
                    </td>
                    <td class="td" style="vertical-align: top">
                        <asp:DropDownList ID="ddlRig" runat="server" CssClass="dropdownlist" AutoPostBack="true" onchange="On_Rig_Change();" OnSelectedIndexChanged="ddlRig_SelectedIndexChanged">
                        </asp:DropDownList>
                    </td>
                    <td class="td_caption">
                        <span class="star">*</span>&nbsp;Project No.</td>
                    <td class="td">
                        <asp:TextBox ID="tbProject_No_Oper_Location" runat="server" CssClass="textbox_readonly" OnKeyDown="return RejectInput();"
                            Width="350px" MaxLength="1"></asp:TextBox>
                        &nbsp;</td>
                </tr>
                <tr>
                    <td class="td_caption" style="vertical-align: top">
                        <span class="star">*</span> Event  : Date/Time
                    </td>
                    <td class="td" style="vertical-align: top">

                        <asp:TextBox ID="tbEvent_Dt" runat="server" CssClass="textbox" MaxLength="10"
                            Width="70px" OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);"
                            AutoCompleteType="Disabled"></asp:TextBox>
                        &nbsp;<asp:TextBox ID="tbEvent_Dt_Time" runat="server" CssClass="textbox" Width="40px"
                            OnKeyUp="return TimeMask(this);" OnBlur=" return CheckTimeOnBlur(this)" MaxLength="5"></asp:TextBox>&nbsp;
                    </td>
                </tr>


                <tr>
                    <td class="td_line" colspan="4"></td>
                </tr>
                <tr>

                    <td class="td_caption"><span class="star">* </span>Reported by party
                    </td>
                    <td class="td">

                        <asp:DropDownList ID="ddlReported_By_Party" runat="server" CssClass="dropdownlist" onchange="  set_Emp_Reported_By('CNTL');">
                            <asp:ListItem Value="" Selected="True"></asp:ListItem>
                            <asp:ListItem Value="SEROS">SEROS</asp:ListItem>
                            <asp:ListItem Value="Operator">Operator</asp:ListItem>
                            <asp:ListItem Value="Visitor">Visitor</asp:ListItem>
                            <asp:ListItem Value="Subcontractor">Subcontractor</asp:ListItem>
                            <asp:ListItem Value="Other">Other</asp:ListItem>
                        </asp:DropDownList>


                    </td>
                    <td class="td_caption">Reported by
                    </td>
                    <td class="td" colspan="3">
                        <asp:TextBox ID="tbReported_By_Name" runat="server" CssClass="textbox"
                            Width="250px" MaxLength="30"></asp:TextBox>
                        <div id="ibtnFs_Emp_Namediv">
                            <asp:ImageButton ID="ibtnFs_Emp_Name"
                                runat="server" OnClientClick="ShowFsEmployee();return false;" ImageAlign="Middle"
                                ImageUrl="~/Images/Icons/search.gif" ToolTip="Find FS Employee" CssClass="image_search" />
                        </div>
                    </td>

                </tr>

                <tr>
                    <td class="td_line" colspan="4"></td>
                </tr>

                <tr>


                    <td class="td_caption">
                        <span class="star">*</span>&nbsp;Location of Hazard&nbsp;
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbWork_Location_Name" runat="server" CssClass="textbox_readonly"
                            MaxLength="1" Width="260px" OnKeyDown="return RejectInput();"></asp:TextBox>
                        <asp:ImageButton ID="ibtnWork_Location" runat="server" CssClass="image_search" ImageAlign="Middle"
                            ImageUrl="~/Images/Icons/search.gif" OnClientClick="Show_Work_Location(); return false;"
                            ToolTip="Find Work Location" />
                    </td>
                    <td class="td_caption"><span class="star">*</span> Type of Hazard

                    </td>
                    <td class="td">
                        <asp:DropDownList ID="ddlHaz_Type_Name" runat="server" CssClass="dropdownlist" onchange="Set_Haz_Type_Id();">
                        </asp:DropDownList>
                    </td>
                    <td class="td_caption">&nbsp;</td>
                    <td class="td">&nbsp;</td>
                </tr>
                <tr>
                    <td class="td_caption">Timeout For Safety
                    </td>
                    <td class="td" style="vertical-align: top">
                        <asp:CheckBox ID="chkTimeout_For_Safety" runat="server" CssClass="checkbox" />
                    </td>
                </tr>
                <tr>
                    <td class="td_line" colspan="4"></td>
                </tr>

                <tr>
                    <td class="td_caption" style="vertical-align: top">
                        <span class="star">*</span> Hazard Desc<br />
                        (200 chars.)
                    </td>
                    <td class="td">
                        <asp:TextBox ID="tbHazard_Desc" runat="server" CssClass="textbox" Width="350px"
                            onkeyPress="CheckMaxLen(this,200);" TextMode="MultiLine" Height="50px" onblur="return fncMultilineTBOnBlur(this,200);"></asp:TextBox>
                    </td>
                    <td class="td_caption" style="vertical-align: top">Action Taken<br />
                        (200 chars.)</td>
                    <td class="td" style="vertical-align: top; margin-left: 40px;">
                        <asp:TextBox ID="tbAction_Taken" runat="server" CssClass="textbox" onkeyPress="CheckMaxLen(this,200);"
                            Height="50px" onblur="return fncMultilineTBOnBlur(this,200);" TextMode="MultiLine"
                            Width="350px"></asp:TextBox>
                    </td>
                </tr>
                <tr>
                    <td class="td_line" colspan="4"></td>
                </tr>
                <tr>
                    <td class="td_caption"><span class="star">*</span> Responsible Dept 
                    </td>
                    <td class="td">

                        <asp:DropDownList ID="ddlResponsible_Dept" runat="server" CssClass="dropdownlist" onclick="check_Clik_Dept_Rank_Rig_Selected(this);"
                            AutoPostBack="true" Width="130px" OnSelectedIndexChanged="ddlResponsible_Dept_SelectedIndexChanged">
                        </asp:DropDownList>

                    </td>
                    <td class="td_caption"><span class="star">*</span> Responsible position</td>
                    <td class="td">
                        <asp:DropDownList ID="ddlResponsible_Rank" runat="server" CssClass="dropdownlist" Width="170px" onclick="check_Clik_Dept_Rank_Rig_Selected(this);" onchange="Set_Reported_Rank_Id(this);">
                        </asp:DropDownList>
                    </td>
                </tr>
                <tr>
                    <td class="td_caption">Close out Date/Time</td>
                    <td class="td">
                        <asp:TextBox ID="tbClose_Out_Dt" runat="server" CssClass="textbox" MaxLength="10" onchange="Set_Status();"
                            Width="70px" OnKeyUp="return DateMask(this);" OnBlur="return CheckDateOnBlur(this);Set_Status();"
                            AutoCompleteType="Disabled"></asp:TextBox>
                        &nbsp;<asp:TextBox ID="tbClose_Out_Dt_Time" runat="server" CssClass="textbox" onchange="Set_Status();"
                            Width="40px" OnKeyUp="return TimeMask(this);" OnBlur=" return CheckTimeOnBlur(this);Set_Status();"
                            MaxLength="5"></asp:TextBox>&nbsp;
                    </td>
                </tr>
                <tr>
                    <td class="td_line" colspan="4"></td>
                </tr>

                <tr>
                    <td class="td_caption">
                        <span class="star">*</span>&nbsp;Status
                    </td>
                    <td class="td">
                        <asp:DropDownList ID="ddlHaz_ID_Card_Status" runat="server" CssClass="dropdownlist" onchange="Set_Status_Status();">
                            <asp:ListItem Value=""></asp:ListItem>
                            <asp:ListItem Value="O" Selected="True">Open</asp:ListItem>
                            <asp:ListItem Value="C">Closed</asp:ListItem>
                        </asp:DropDownList>
                    </td>
                  
                </tr>

            </table>
            <br />
            <input id="tbHaz_Card_Id_Hidden" runat="server" name="tbHaz_Card_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbPrj_Contract_Id_Hidden" runat="server" name="tbPrj_Contract_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbReported_By_Fs_Emp_Id_Hidden" runat="server" name="tbReported_By_Fs_Emp_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbWork_Location_Id_Hidden" runat="server" name="tbWork_Location_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbHaz_Type_Id_Hidden" runat="server" name="tbHaz_Type_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbResp_Dept_Id_Hidden" runat="server" name="tbResp_Dept_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbResp_Rank_Id_Hidden" runat="server" name="tbResp_Rank_Id_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbHaz_ID_Card_Status_Hidden" runat="server" name="tbHaz_ID_Card_Status_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden"
                style="z-index: 104; left: 23px; width: 24px; position: absolute; top: 290px; height: 24px"
                type="hidden" />
        </div>

        <script language="javascript" type="text/javascript">
            set_Emp_Reported_By('PAGE_LOAD');

        </script>
    </form>
</body>
</html>
