<%@ Page Language="C#" AutoEventWireup="true" CodeFile="frmHSE_Drill_Record_Event.aspx.cs"
    Inherits="Quality_And_Safety_frmHSE_Drill_Record_Event" %>

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head id="Head1" runat="server">
    <title>HSE Drill Record Event</title>

    <link href="../../StyleSheet.css" type="text/css" rel="stylesheet" />
    <script type="text/javascript" language="javascript" src="../../Javascript/generic.js"> </script> 
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_Search.js"> </script>
    <script type="text/javascript" language="javascript" src="../../Javascript/Open_ErrorWin.js"> </script>   
    <script type="text/javascript" language="javascript" src="../../JavaScript/jquery.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/bootstrap.min.js"></script>
    <script type="text/javascript" language="javascript" src="../../JavaScript/CommonModal.js"></script>
    
    <link href="../../BootstrapStyleSheet.min.css" type="text/css" rel="stylesheet" /> 
    <script type="text/javascript">
        window.onload = function () {  }




        //function ShowMainData() {
        //    SetPostbackFlag("SEARCH");
        //    Open_Search_Window('EQUIPMENT_PART', document.forms[0].name, 'tbDrill_Rec_Event_Id_Hidden', 'tbEquip_Make_Name', '', '', 'Y', 'N', 'N');
        //    return;
        //}


        /// Determine whether page has to be posted back by passing a flag to a hidden textbox.
        function SetPostbackFlag(strFlag) {
            document.getElementById('<%=tbPostbackFlag_Hidden.ClientID%>').value = strFlag;
            return true;
        }

        function ValidateInsert(lnkUpdate, Type) {
            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';



            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

            var tbDrill_Rec_Event_Time = grdRow.getElementsByTagName("input")[0];
            var tbDrill_Rec_Event_Descc = grdRow.getElementsByTagName("textarea")[0];//.id;


            if (tbDrill_Rec_Event_Time.value == "") {
                msg += "- Event Time must be entered.<br><br>";

            }

            if (alltrim(tbDrill_Rec_Event_Descc.value) == "") {
                msg += "- Event description must be entered.<br><br>";

            }

            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }

        /// Set a mask for a Time field.
        function TimeMask(obj) {
            if (!obj.value == "" && !checkTime(obj.value)) {
                if ((event.keyCode == 8) || (event.keyCode == 46) || (event.keyCode >= 35 && event.keyCode <= 40))
                    return;

                var objDate = obj;
                var len = objDate.value.length;

                if (event.keyCode > 31 && ((event.keyCode < 48 || event.keyCode > 58) && (event.keyCode < 96 || event.keyCode > 105))) {
                    objDate.value = objDate.value.substr(0, len - 1);
                    return;
                }
                if (len == 2) {
                    objDate.value += ":";
                }
                if (len == 3) {
                    objDate.value = objDate.value.substr(0, len - 1);
                    objDate.value += ":";
                    return;
                }
            }
        }


        function isPositiveIntegerWith(strLineval) {
            var strLine1 = ltrim(rtrim(strLineval));
            if (isInteger(strLine1)) {
                if (strLine1 >= 0) {
                    return true;
                }
                else {
                    alert("Please enter positive integers only");
                    return false;
                }
            }
            else {
                alert("Please enter positive integers only");
                return false;
            }
        }

        function CheckTime_HH_MM_SS_OnBlur(obj) {

            
            var len = obj.value.length;

            if (len == 8) {


                var nArr = obj.value.split(':');

                if (nArr.length == 3)
                {
                    var HH = isPositiveIntegerWith(nArr[0]);
                    if (HH == false) { return false; }


                    var MM = isPositiveIntegerWith(nArr[1]);
                    if (MM == false) { return false; }


                    var SS = isPositiveIntegerWith(nArr[2]);
                    if (SS == false) { return false; }


                    if (nArr[0] < 0 || nArr[0] > 23) {
                        alert("Hours must be in the range [0-23]");
                        obj.focus(); return false;
                    }

                    if (nArr[1] < 0 || nArr[1] > 59) {
                        alert("Minutes must be in the range [0-59]");
                        obj.focus(); return false;
                    }

                    if (nArr[2] < 0 || nArr[2] > 59) {
                        alert("Seconds must be in the range [0-59]");
                        obj.focus(); return false;
                    }
                }

                else {

                    alert('Invalid Time  entered!');
                    obj.focus();
                    return false;
                }


            }
            else {
                if (len != 0) {
                    alert('Invalid Time entered!');
                    obj.focus();
                    return false;
                }
            }


        }
        /// Set a mask for a Time field.
        function TimeMask_HH_MM_SS(obj) {
            if (!obj.value == "" ) {
                if ((event.keyCode == 8) || (event.keyCode == 46) || (event.keyCode >= 35 && event.keyCode <= 40))
                    return;

                var objDate = obj;
                var len = objDate.value.length;

                if (event.keyCode > 31 && ((event.keyCode < 48 || event.keyCode > 58) && (event.keyCode < 96 || event.keyCode > 105))) {
                    objDate.value = objDate.value.substr(0, len - 1);
                    return;
                }
                if (len == 2) {
                    objDate.value += ":";
                }
                if (len == 3) {
                    objDate.value = objDate.value.substr(0, len - 1);
                    objDate.value += ":";
                    return;
                }
                if (len == 5) {
                    objDate.value += ":";
                }
                if (len == 6) {
                    objDate.value = objDate.value.substr(0, len - 1);
                    objDate.value += ":";
                    return;
                }
            }
        }

        function ValidateUpdate(lnkUpdate, Type) {


            SetPostbackFlag(Type);
            var msg = "";
            var strServerDt = '<%= Session["ServerDt"].ToString() %>';


            var grdRow = lnkUpdate.parentNode.parentNode;
            var grdControl = grdRow.getElementsByTagName("input");

            var tbDrill_Rec_Event_Time = grdRow.getElementsByTagName("input")[0];
            var tbDrill_Rec_Event_Desc = grdRow.getElementsByTagName("textarea")[0];//.id;


            if (tbDrill_Rec_Event_Time.value == "") {
                msg += "- Event Time must be entered.<br><br>";

            }

            if (alltrim(tbDrill_Rec_Event_Desc.value) == "") {
                msg += "- Event description must be entered.<br><br>";

            }

            if (msg == "") {

                return true;

            }
            else {
                ShowErrorWin1(msg);
                return false;
            }
        }



        function ChkPrintStatus(id) {

            var rows = document.getElementById('<%=grdContact.ClientID %>').getElementsByTagName('TR');
               for (var i = 0; i < rows.length; i++) {
                   rows[i].className = 'GridView_RowStyle'; //if its your default color
               }
               document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_SelectedRowStyle';


               var chkdeletestatus = confirm("Are you sure you want to Delete this Record?");
               if (chkdeletestatus == true) {
                   return true;
               }
               else {
                   document.getElementById(id.uniqueID).parentNode.parentNode.className = 'GridView_RowStyle';
                   return false;
               }
           }

           function CheckMaxLen(obj, length) {
               checkTextAreaMaxLength(obj, event, length);
           }
    </script>

</head>
<body class="body" onkeydown="if (event.keyCode==13) {event.keyCode=9; return event.keyCode }">
    <form id="frmHSE_Drill_Record_Event" runat="server">
        <div style="left: 0px; width: 100%; position: absolute; top: 0px; height: 88%">
            <table style="width: 100%" class="table_header">
                <tr>
 
                    <td class="td_button">
                        <asp:Button ID="btnSearch" runat="server" Text="Search" Width="100%" CssClass="td_button" Visible="false" />

                    </td>
             

                    <td class="td_button">
                        <asp:Button ID="btnClear" runat="server" Text="Clear" Width="100%" CssClass="td_button" Visible="false"/></td>

                    <td class="td_button">&nbsp;</td>
                    <td class="td_header" style="width: 46%">Chronological Order of Events during the Drill</td>
                </tr>
            </table>
            <br />

            <table class="table">
                <tr>
                    <td style="width: 2%">&nbsp;</td>
                </tr>
                <tr>
                    <td></td>
                    <td>

                        <div id="divHelpData" class="div_gridview" style="width: 75%;">
                            <asp:GridView ID="grdContact" CssClass="GridView" Width="98%" runat="server"
                                AutoGenerateColumns="False" DataKeyNames="Drill_Rec_Event_Id"
                                ShowFooter="True" OnRowCommand="grdContact_RowCommand" OnRowUpdating="grdContact_RowUpdating" OnRowCancelingEdit="grdContact_RowCancelingEdit" OnRowEditing="grdContact_RowEditing">
                                <Columns>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="ID" Visible="false">
                                        <EditItemTemplate>
                                            <asp:Label ID="lblId" CssClass="textbox" runat="server" Text='<%# Bind("Drill_Rec_Event_Id") %>'></asp:Label>
                                        </EditItemTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblId0" runat="server" Text='<%# Bind("Drill_Rec_Event_Id") %>'></asp:Label>
                                        </ItemTemplate>
                                        <ItemStyle />
                                        <HeaderStyle HorizontalAlign="Left"></HeaderStyle>
                                    </asp:TemplateField>

                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Event Time(HH:MM:SS)*" ItemStyle-CssClass="textbox" FooterStyle-CssClass="textbox">
                                        <EditItemTemplate>
                                            <asp:TextBox ID="txtEdit_Drill_Rec_Event_Time" runat="server" Text='<%# Bind("Drill_Rec_Event_Time") %>'
                                                CssClass="textbox" Width="60px"
                                                OnKeyUp="return TimeMask_HH_MM_SS(this);" OnBlur=" return CheckTime_HH_MM_SS_OnBlur(this)" MaxLength="8"></asp:TextBox>
                                        </EditItemTemplate>
                                        <FooterTemplate> 
                                            <asp:TextBox ID="txtDrill_Rec_Event_Time" runat="server" CssClass="textbox" Width="60px"
                                            OnKeyUp="return TimeMask_HH_MM_SS(this);" OnBlur=" return CheckTime_HH_MM_SS_OnBlur(this)" MaxLength="8"></asp:TextBox> 
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblDrill_Rec_Event_Time" runat="server" Text='<%# Bind("Drill_Rec_Event_Time") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="80px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="80px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="80px" />
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Event Description  * (200 Chars.)" ItemStyle-CssClass="textbox" FooterStyle-CssClass="textbox">
                                        <EditItemTemplate>
                                            <asp:TextBox ID="txtEdit_Drill_Rec_Event_Desc" runat="server" CssClass="textbox" MaxLength="200" Text='<%# Bind("Drill_Rec_Event_Desc") %>'
                                                Width="690px" TextMode="MultiLine" Height="30px" onkeyPress="CheckMaxLen(this,200);"
                                                onblur="return fncMultilineTBOnBlur(this,200);"></asp:TextBox>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:TextBox ID="txtDrill_Rec_Event_Desc" runat="server" CssClass="textbox" MaxLength="200"
                                                Width="690px" TextMode="MultiLine" Height="30px" onkeyPress="CheckMaxLen(this,200);"
                                                onblur="return fncMultilineTBOnBlur(this,200);"></asp:TextBox>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:Label ID="lblDrill_Rec_Event_Desc" runat="server" Text='<%# Bind("Drill_Rec_Event_Desc") %>'></asp:Label>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="770px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="770px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="770px" />
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderStyle-HorizontalAlign="Left" HeaderText="Insert" ShowHeader="False">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="lbkUpdate" runat="server" CausesValidation="True" CommandName="Update" Text="Update" OnClientClick="return ValidateUpdate(this,'Update')"></asp:LinkButton>
                                            <asp:LinkButton ID="lnkCancel" runat="server" CausesValidation="False" CommandName="Cancel" Text="Cancel"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkAdd" runat="server" CausesValidation="False" CommandName="Insert" Text="Insert" OnClientClick="return ValidateInsert(this,'Insert')"></asp:LinkButton>
                                        </FooterTemplate>

                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkEdit" runat="server" CausesValidation="False" CommandName="Edit" Text="Edit"></asp:LinkButton>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="120px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                    </asp:TemplateField>
                                    <asp:TemplateField HeaderText="Delete">
                                        <EditItemTemplate>
                                            <asp:LinkButton ID="ilnkDelete" runat="server"></asp:LinkButton>
                                        </EditItemTemplate>
                                        <FooterTemplate>
                                            <asp:LinkButton ID="lnkDelete" runat="server"></asp:LinkButton>
                                        </FooterTemplate>
                                        <ItemTemplate>
                                            <asp:LinkButton ID="lnkDelete" CommandName="cmdDelete" Text="Delete" runat="server"
                                                CommandArgument='<%# Eval("Drill_Rec_Event_Id") %>' OnClientClick="javascript:return ChkPrintStatus(this);"></asp:LinkButton>
                                        </ItemTemplate>
                                        <HeaderStyle HorizontalAlign="Left" Width="120px"></HeaderStyle>
                                        <ItemStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                        <FooterStyle HorizontalAlign="Center" CssClass="textbox" Width="120px" />
                                    </asp:TemplateField>
                                </Columns>

                                  <RowStyle CssClass="GridView_RowStyle" />
                             
                            <SelectedRowStyle CssClass="GridView_SelectedRowStyle" />
                            <HeaderStyle  CssClass="GridView_HeaderStyle" Height="20px" />
                            <AlternatingRowStyle CssClass="GridView_AlternatingRowStyle" />
                        </asp:GridView>
                             
                        </div>
                    </td>
                </tr>
            </table>

            <input id="tbDrill_Record_Hdr_Id_Hidden" runat="server" name="tbDrill_Record_Hdr_Id_Hidden"
                style="z-index: 104; left: 312px; width: 24px; position: absolute; top: 289px; height: 24px"
                type="hidden" value="" />
            <input id="tbDrill_Dt_Id_Hidden" runat="server" name="tbDrill_Dt_Id_Hidden"
                style="z-index: 104; left: 312px; width: 24px; position: absolute; top: 289px; height: 24px"
                type="hidden" value="" />

            <input id="tbPostbackFlag_Hidden" runat="server" name="tbPostbackFlag_Hidden" style="z-index: 104; left: 165px; width: 24px; position: absolute; top: 291px; height: 24px"
                type="hidden" />
        </div>
    </form>
</body>
</html>
