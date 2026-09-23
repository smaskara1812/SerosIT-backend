<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmActivity_Monitor.aspx.cs"
    Inherits="Quality_And_Safety_frmActivity_Monitor" %>

<%--
<%@ Register assembly="AjaxControlToolkit" namespace="AjaxControlToolkit" tagprefix="AjaxToolKit" %>
--%>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>Activity Monitor </title>
    <link href="../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../JavaScript/CommonModal.js"></script>
    
    <link href="../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" />  
 

    <script type="text/javascript">

        function validate(strFlag) {
            var msg = "";

            /// Set a value to indicate the control/event that causes a postback.
            SetPostbackFlag(strFlag);

            ///Checking whether record already exists,if yes Add is not allowed ,only update is allowed

            if (document.getElementById('<%=tbActivity_Monitor_Id_Hidden.ClientID%>').value != "") {
                alert("- You are currently in update mode, New record will not be added in this mode.");
                return false;
            }

            var strServerDt = '<%= Session["ServerDt"].ToString() %>';
            var strToDt = "";


            ///Activity vlidation
            if (document.getElementById('<%=tbActivity_Id_Hidden.ClientID%>').value == "") {
                document.getElementById('<%=tbActivity_Name.ClientID%>').focus();
                msg += "- Activity must be selected<br><br>";
            }

            ///Schedule Date Validtion

            if (document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value == "") {
                document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').focus();
                msg += "- Schedule Date must be entered <br><br>";
            }
            else {
                if (!checkDate(document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value)) {
                    document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').focus();
                    msg += "- Invalid Schedule Date <br><br>";
                }
            }
            ///RIG validation
            if (document.getElementById('<%=tbActivity_Location_Hidden.ClientID%>').value == "R" || document.getElementById('<%=tbActivity_Location_Hidden.ClientID%>').value == "R") {
                if (document.getElementById('<%=tbRig_Id_Hidden.ClientID%>').value == "") {
                    document.getElementById('<%=tbRig_Name.ClientID%>').focus();
                    msg += "- Rig must be selected<br><br>";
                }
            }

            if (msg == "") {
                return true;
            } else {
                //alert("The following errors were encountered \n" + msg);
                ShowErrorWin1(msg);
                return false;
            }
        }


        function ValidateUpdate() {
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';
            var msg = "";
            

            SetPostbackFlag("UPDATE");
            if (document.getElementById('<%=tb_Compl_Dt_Exists_Hidden.ClientID%>').value == "Y") {
                alert("Activity already completed. Data can not be altered");
                return false;
            }

            if (document.getElementById('<%=tbActivity_Monitor_Id_Hidden.ClientID%>').value == "") {
                alert("Select the record to update");
                return false;
            }


            if (document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value == "") {
                document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').focus();
                  msg += "- Schedule Date must be entered <br><br>";
              }
              else {
                  if (!checkDate(document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value)) {
                      document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').focus();
                    msg += "- Invalid Schedule Date <br><br>";
                }
            }

            //validate for tbActivity_Monitor_Dt if change  then planning remark must be entered    	     

            if (document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value != document.getElementById('<%=tbPrev_Activity_Monitor_Dt_Hidden.ClientID%>').value) {
                if (document.getElementById('<%=tbPlanning_Remark.ClientID%>').value == "") {
                    msg += "- Planning Remark must be entered <br><br>";
                    document.getElementById('<%=tbPlanning_Remark.ClientID%>').focus();
                }
            }

            /// date Completion validation

            if (document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value != "") {
                if (!checkDate(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value)) {
                    msg += "- Invalid Completion Date<br><br>";
                    document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').focus();
                }
                else {
                    if (compareDates(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value, 'dd/MM/yyyy', strServerDt, 'dd/MM/yyyy') == 0)
                    { }
                    else {
                        msg += "- Completion Date must be less than equal to current date<br><br>";
                        document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').focus();
                    }
                }
                if (document.getElementById('<%=tbCompletion_Remark.ClientID%>').value == "") {
                    msg += "- Completion Remark must be entered<br><br>";
                    document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').focus();
                }


            }
            if (document.getElementById('<%=ddlNextScheduleRequired.ClientID%>').value == "Select") {
                msg += "- Select whether to create Next Schedule (Yes / No) <br><br>";
                document.getElementById('<%=ddlNextScheduleRequired.ClientID%>').focus();
            }

            if (document.getElementById('<%=ddlNextScheduleRequired.ClientID%>').value == "Yes") {

                //  	                    if(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value == "")
                //			                {   document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').focus();
                //			                    msg += "- Completion Date must be entered <br><br>";
                //			                }
                ///Monitor Date Validtion

                if (document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value == "") {
                    document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').focus();
                    msg += "- Next Monitor Date must be entered <br><br>";
                }
                else {
                    if (!checkDate(document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value)) {
                        document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').focus();
                        msg += "- Invalid Next Monitor Date <br><br>";
                    }

                    if (compareDates(document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value, 'dd/MM/yyyy', document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value, 'dd/MM/yyyy') == 1) {
                        msg += "- Next Schedule Date must be greater than Schedule Date<br><br>";
                        document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').focus();
                    }
                }
            }

            if (msg == "") {
                return true;
            }
            else {
                ShowErrorWin1(msg);
                return false;

            }
        }

        function ShowActivityMonitor() {
            SetPostbackFlag("SEARCH");
            var strSearchString = "%";
            Open_Search_Window('ACTIVITY_MONITOR', document.forms[0].name, 'tbActivity_Monitor_Id_Hidden', 'tbActivity_Name', '', strSearchString, 'Y', 'N', 'N');
            return;
        }

        function ShowRig() {
            if (document.getElementById('<%=tbActivity_Id_Hidden.ClientID%>').value == "") {
                alert("Activity must be selected first");
                document.getElementById('<%=tbActivity_Name.ClientID%>').focus();
                return false;
            }
            
            SetPostbackFlag("RIG");
            var strSearchString = "%";
            Open_Search_Window('RIG', document.forms[0].name, 'tbRig_Id_Hidden', 'tbRig_Name', '', strSearchString, 'Y', 'Y', 'N');
            return;
        }

        function ShowActivity() {
            SetPostbackFlag("ACTIVITY");
            var strSearchString = "%";
            Open_Search_Window('ACTIVITY', document.forms[0].name, 'tbActivity_Id_Hidden', 'tbActivity_Name', '', strSearchString, 'Y', 'Y', 'N');
            return;
        }

        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }

        ///get and set the calculation gap which is days between schedule  date and completion date
        function GetCopmepletionGap() {
        
            CheckDateOnBlur(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>'))

            if (document.getElementById('<%=tbActivity_Monitor_Id_Hidden.ClientID%>').value != "") {
                if (document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value != "") {
                    var msg = "";

                    if (!checkDate(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value)) {
                        msg += "- Invalid Completion Date<br><br>";
                        document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').focus();

                    }
                    if (msg == "") {

                        var days = getDaysBetween(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value, document.getElementById('<%=tbActivity_Monitor_Dt.ClientID%>').value);
                        //alert(days);
                        document.getElementById('<%=tbMonitor_Compl_Gap.ClientID%>').value = days;
                        return true;
                    }
                    else {  //ShowErrorWin(msg);        

                        return false;
                    }

                } //if(document.getElementById('<%=tbActivity_Compl_Dt.ClientID%>').value != "")
                else {
                    document.getElementById('<%=tbMonitor_Compl_Gap.ClientID%>').value = "";
                }
                return true;
            } // if(document.getElementById('<%=tbActivity_Monitor_Id_Hidden.ClientID%>').value != "") 
            return true;
        }  //  function GetCopmepletionGap()

        function Check_Next_Schedule_Required() {

            if (document.getElementById('<%=ddlNextScheduleRequired.ClientID%>').selectedIndex == 2) {
                document.getElementById('<%=tbNextActivity_Monitor_Dt_Hidden.ClientID%>').value = document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value;
                document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value = "";
                document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').disabled = true;
            }
            else if (document.getElementById('<%=ddlNextScheduleRequired.ClientID%>').selectedIndex == 1) {
                document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').value = document.getElementById('<%=tbNextActivity_Monitor_Dt_Hidden.ClientID%>').value;
                document.getElementById('<%=tbNextActivity_Monitor_Dt.ClientID%>').disabled = false;
            }
        }
            

    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="form2" runat="server">
     
    <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
        <table style="width: 100%" class="table_header">
            <tr>
                
                <td class="td_button">
                    <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" OnClientClick="ShowActivityMonitor()"
                        CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnAdd" runat="server" Text="Add" Width="100%" OnClick="btnAdd_Click"
                        CssClass="td_button" />
                </td>
                <td class="td_button">
                    <asp:Button ID="btnUpdate" runat="server" Text="Update" Width="100%" CssClass="td_button"
                        OnClick="btnUpdate_Click" />
                </td>
               <%-- <td class="td_button">
                    <asp:Button ID="btnDelete" runat="server" Text="Delete" Width="100%" CssClass="td_button" />
                </td>--%>
                <td class="td_button">
                    <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button"
                        OnClientClick="SetPostbackFlag('CLEAR');" OnClick="btnClear_Click" />
                </td>
                <%--<td class="td_button">
                    <asp:Button ID="btnPrint" runat="server" Text="Print" Width="100%" CssClass="td_button" />
                </td>--%>
                <td class="td_button">
                    &nbsp;
                </td>
                <td class="td_header" style="width: 40%">
                    Activity Monitor Informtion
                </td>
            </tr>
        </table>
        <br />
        <table cellpadding="0" cellspacing="0" class="table">
            <tr>
                <td class="td_caption" style="width: 32%;">
                    <span class="star">*</span>&nbsp;Activity
                </td>
                <td class="td" style="width: 80%" colspan="2">
                    <asp:TextBox ID="tbActivity_Name" runat="server" CssClass="textbox_readonly" ReadOnly="False"
                        Width="445px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtnActivity_Name"
                            runat="server" OnClientClick="ShowActivity();" ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif"
                            ToolTip="Find Activity" CssClass="image_search" />&nbsp;
                    
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 32%;">
                    Rig
                </td>
                <td class="td" style="width: 80%" colspan="2">
                    <asp:TextBox ID="tbRig_Name" runat="server" CssClass="textbox_readonly" ReadOnly="False"
                        Width="105px" MaxLength="1"></asp:TextBox>&nbsp;<asp:ImageButton ID="ibtnRig" runat="server"
                            OnClientClick="ShowRig();" ImageAlign="Middle" ImageUrl="~/Images/Icons/search.gif"
                            ToolTip="Find RIG" CssClass="image_search" />
                      <img src="../Images/Icons/Clearfield.jpg" title="Clear Field" style="cursor:pointer; height:20px;"  id="imgfieldRig"
                        onclick="javascript:return clearInput('<%= tbRig_Name.ClientID %>','<%= tbRig_Id_Hidden.ClientID %>');" />                             
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 32%">
                    <span class="star">*</span>&nbsp;Schedule Date
                </td>
                <td class="td" style="width: 25%" colspan="2">
                    <asp:TextBox ID="tbActivity_Monitor_Dt" runat="server" CssClass="textbox" Height="15px"
                        MaxLength="10" Width="70px"></asp:TextBox>
                    &nbsp;&nbsp;&nbsp;
                    <asp:Label ID="lblOriginal_Monitor_Dt" runat="server" CssClass="label" Visible="False">Original Date</asp:Label>
                    &nbsp;
                    <asp:TextBox ID="tbOriginal_Monitor_Dt" runat="server" CssClass="textbox_readonly"
                        Height="15px" OnKeyDown="return RejectInput();" MaxLength="10" Width="70px" Visible="False"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 32%">
                    Planning Remark
                </td>
                <td class="td" style="width: 5%">
                    <asp:TextBox ID="tbPlanning_Remark" runat="server" CssClass="textbox" MaxLength="50"
                        Width="360px"></asp:TextBox>
                </td>
                <td class="td" style="width: 95%">
                    <br />
                </td>
            </tr>
        </table>
        <br />
        <% if (tbActivity_Monitor_Id_Hidden.Value != "")
           { %>
        <table cellpadding="0" cellspacing="0" class="table_section">
            <tr>
                <td class="td_section" style="width: 20%">
                    Grouping &amp; Validity
                </td>
                <td>
                    &nbsp;
                </td>
            </tr>
        </table>
        <br />
        <table cellpadding="0" cellspacing="0" class="table">
            <tr>
                <td class="td_caption" style="width: 20%">
                    Completion Date
                </td>
                <td class="td" style="width: 25%">
                    <asp:TextBox ID="tbActivity_Compl_Dt" runat="server" CssClass="textbox" Height="15px"
                        MaxLength="10" Width="70px"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 20%; height: 27px;">
                    Completion Remark
                </td>
                <td class="td" style="width: 80%">
                    <asp:TextBox ID="tbCompletion_Remark" runat="server" CssClass="textbox" MaxLength="100"
                        Width="700px"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 20%; height: 27px;">
                    Completion Gap
                </td>
                <td class="td" style="width: 80%">
                    <asp:TextBox ID="tbMonitor_Compl_Gap" runat="server" CssClass="textbox" MaxLength="10"
                        Width="50px"></asp:TextBox>
                </td>
            </tr>
        </table>
        <br />
        <% if (tbActivity_Compl_Dt.Text == "")
           { %>
        <table cellpadding="0" cellspacing="0" class="table_section">
            <tr>
                <td class="td_section" style="width: 20%">
                    Next Schedule
                </td>
                <td>
                    &nbsp;
                </td>
            </tr>
        </table>
        <br />
        <table cellpadding="0" cellspacing="0" class="table">
            <tr>
                <td class="td_caption" style="width: 32%; height: 15px;">
                    <span class="star">*</span>&nbsp;Next Schedule Required
                </td>
                <td class="td" style="width: 25%; height: 15px;" colspan="2">
                    <asp:DropDownList ID="ddlNextScheduleRequired" runat="server" CssClass="dropdownlist"
                        Width="90px" Enabled="True" onchange="Check_Next_Schedule_Required();">
                        <asp:ListItem>Select</asp:ListItem>
                        <asp:ListItem Selected="True">Yes</asp:ListItem>
                        <asp:ListItem>No</asp:ListItem>
                    </asp:DropDownList>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 32%">
                    <span class="star">*</span>&nbsp;Next Schedule Date
                </td>
                <td class="td" style="width: 25%" colspan="2">
                    <asp:TextBox ID="tbNextActivity_Monitor_Dt" runat="server" CssClass="textbox" Height="15px"
                        MaxLength="10" Width="70px"></asp:TextBox>
                </td>
            </tr>
            <tr>
                <td class="td_caption" style="width: 32%">
                    Next Planning Remark
                </td>
                <td class="td" style="width: 5%">
                    <asp:TextBox ID="tbNextPlanning_Remark" runat="server" CssClass="textbox" MaxLength="50"
                        Width="360px"></asp:TextBox>
                </td>
                <td class="td" style="width: 95%">
                    <br />
                </td>
            </tr>
            <% } %>
        </table>
        <% } %>
        <input id="tbActivity_Monitor_Id_Hidden" runat="server" name="tbActivity_Monitor_Id_Hidden"
            style="z-index: 104; left: 286px; width: 24px; position: absolute; top: 160px;
            height: 24px" type="hidden" />
        <input id="tbActivity_Id_Hidden" runat="server" name="tbActivity_Id_Hidden" style="z-index: 104;
            left: 339px; width: 24px; position: absolute; top: 158px; height: 24px" type="hidden" />
        <input id="tbRig_Id_Hidden" runat="server" name="tbRig_Id_Hidden" style="z-index: 104;
            left: 389px; width: 24px; position: absolute; top: 158px; height: 24px" type="hidden" />
        <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104;
            left: 485px; width: 24px; position: absolute; top: 155px; height: 24px" type="hidden" />
        <input id="tbActivity_Location_Hidden" runat="server" name="tbActivity_Location_Hidden"
            style="z-index: 104; left: 440px; width: 24px; position: absolute; top: 155px;
            height: 24px" type="hidden" />
        <input id="tb_Compl_Dt_Exists_Hidden" runat="server" name="tb_Compl_Dt_Exists_Hidden"
            style="z-index: 104; left: 440px; width: 24px; position: absolute; top: 155px;
            height: 24px" type="hidden" />
        <input id="Activity_Validity_Days_Hidden" runat="server" name="Activity_Validity_Days_Hidden"
            style="z-index: 104; left: 440px; width: 24px; position: absolute; top: 155px;
            height: 24px" type="hidden" />
        <input id="tbPrev_Activity_Monitor_Dt_Hidden" runat="server" name="tbPrev_Activity_Monitor_Dt_Hidden"
            style="z-index: 104; left: 440px; width: 24px; position: absolute; top: 155px;
            height: 24px" type="hidden" />
        <input id="tbNextActivity_Monitor_Dt_Hidden" runat="server" name="tbNextActivity_Monitor_Dt_Hidden"
            style="z-index: 104; left: 460px; width: 24px; position: absolute; top: 155px;
            height: 24px" type="hidden" />
    </div>
    </form>
</body>
</html>
